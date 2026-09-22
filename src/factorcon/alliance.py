"""Rorqual-only fresh-run identity and personal scratch quota boundaries.

All measurements below concern storage bytes/files, not participant outcomes. No
shared project path is accepted as a download/cache target. Scratch is not archival.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from factorcon.errors import CapacityError, IntegrityError
from factorcon.util import atomic_write_json, utc_now

PERSONAL_ROOT = Path("/scratch/pwa209")
STUDY_ROOT = PERSONAL_ROOT / "cognition-and-consciousness"


def is_rorqual_execution(hostname: str, environment: dict[str, str]) -> bool:
    """Accept verified login naming or CPU node naming plus a Rorqual Slurm allocation."""
    short = hostname.split(".")[0]
    if re.fullmatch(r"rorqual\d+", short):
        return True
    return bool(
        re.fullmatch(r"rc\d+", short)
        and environment.get("SLURM_CLUSTER_NAME") == "rorqual"
        and re.fullmatch(r"\d+", environment.get("SLURM_JOB_ID", ""))
    )


def validate_fresh_root(root: str | Path, *, check_host: bool = True) -> Path:
    """Constrain a fresh run to this study's personal scratch tree, rejecting symlinks.

    The root must be one fresh-* child of STUDY_ROOT, not another user's/group's
    storage. With check_host=False this performs only lexical validation for tests.
    """
    path = Path(root)
    if path.parent != STUDY_ROOT or not re.fullmatch(r"fresh-[A-Za-z0-9_-]+", path.name):
        raise IntegrityError(
            "fresh root must be /scratch/pwa209/cognition-and-consciousness/fresh-*"
        )
    if check_host:
        import pwd

        if pwd.getpwuid(os.getuid()).pw_name != "pwa209" or not is_rorqual_execution(
            socket.gethostname(), dict(os.environ)
        ):
            raise IntegrityError("Rorqual/pwa209 identity required")
        if not PERSONAL_ROOT.is_dir() or path.resolve() != path:
            raise IntegrityError("missing personal scratch mount or redirected study path")
        if PERSONAL_ROOT.stat().st_uid != os.getuid():
            raise IntegrityError("personal scratch root is not owned by current user")
    return path


def read_source_record(root: Path, source: Path) -> dict:
    """Read a same-run immutable source manifest; no data migration or active release switch.

    The initial FRESH_RUN marker remains unchanged when a new source version is added.
    Per-release records bind subsequent jobs to their own exact source bytes.
    """
    initial = json.loads((root / "FRESH_RUN.json").read_text())
    if initial.get("reuse_prior_data") is not False or initial.get("download_root") != str(root):
        raise IntegrityError("fresh-run identity mismatch")
    source = source.resolve()
    if (
        source.name != "source"
        or source.parent.parent != root / "releases"
        or not re.fullmatch(r"[0-9a-f]{40}", source.parent.name)
    ):
        raise IntegrityError("source is not a versioned release inside this fresh run")
    path = source.parent / "RELEASE.json"
    record = json.loads(path.read_text()) if path.exists() else initial
    if record.get("release") != str(source):
        raise IntegrityError("source release identity mismatch")
    return record


@dataclass(frozen=True)
class PersonalQuota:
    """Conservative reported personal usage/limit in decimal bytes and file counts."""

    used_bytes: int
    limit_bytes: int
    used_files: int
    limit_files: int
    report_line: str


def parse_personal_quota(report: str) -> PersonalQuota:
    """Parse only /scratch (user pwa209), never shared filesystem or group free space.

    Human-readable usage is rounded upward by one displayed unit to avoid optimistic
    precision. Unknown formats fail closed; no fallback to df as a personal quota.
    """
    lines = [line for line in report.splitlines() if re.search(r"/scratch\s+\(user pwa209\)", line)]
    if len(lines) != 1:
        raise CapacityError("exactly one personal /scratch (user pwa209) quota row required")
    pattern = (
        r"/scratch\s+\(user pwa209\)\s+(?:->\s*)?([\d.]+)\s*(B|KB|MB|GB|TB)\s*/\s*"
        r"([\d.]+)\s*(B|KB|MB|GB|TB)\s+(?:->\s*)?([\d.]+)\s*([KMG]?)\s*/\s*([\d.]+)\s*([KMG]?)\s*$"
    )
    match = re.search(pattern, lines[0])
    if not match:
        raise CapacityError("unrecognized diskusage_report personal quota format")
    used, unit, limit, limit_unit, files, files_unit, file_limit, file_limit_unit = match.groups()
    sizes = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}
    counts = {"": 1, "K": 1000, "M": 1000**2, "G": 1000**3}
    quota = PersonalQuota(
        int((float(used) + 1) * sizes[unit]),
        int(float(limit) * sizes[limit_unit]),
        int((float(files) + 1) * counts[files_unit]),
        int(float(file_limit) * counts[file_limit_unit]),
        lines[0].strip(),
    )
    if quota.limit_bytes <= 0 or quota.limit_files <= 0:
        raise CapacityError("positive personal quota limits required")
    return quota


def read_personal_quota() -> PersonalQuota:
    """Read fresh personal counters with bounded transient-service retries.

    No payload bytes are written while retrying. Exhaustion raises CapacityError,
    stopping new download submissions while preserving partials. Never substitute
    stale counters or shared filesystem free space for personal quota evidence.
    """
    for attempt in range(3):
        try:
            command = subprocess.run(
                ["diskusage_report"], capture_output=True, text=True, timeout=45
            )
        except (subprocess.TimeoutExpired, OSError):
            command = None
        if command is not None and command.returncode == 0:
            # A malformed successful report is an integrity failure, not transient.
            return parse_personal_quota(command.stdout)
        if attempt < 2:
            time.sleep(5 * (attempt + 1))
    raise CapacityError(
        "personal quota service unavailable after 3 attempts; partials retained, "
        "new transfers stopped until fresh quota is available"
    )


class ScratchQuotaGuard:
    """Serialize per-chunk quota checks; retain 500 GB and 50,000 files by default.

    A monotonic charged-byte bound covers this process's writes between quota reports.
    Other studies' usage is checked periodically; filesystem quotas remain the final
    enforcement mechanism. This is not a storage reservation for this study.
    """

    def __init__(
        self,
        status_path: Path,
        *,
        reserve_bytes: int = 500_000_000_000,
        reserve_files: int = 50_000,
        stale_grace_seconds: float = 0,
        stale_charge_bytes: int = 0,
        stale_charge_files: int = 0,
        stale_reserve_bytes: int | None = None,
        stale_reserve_files: int | None = None,
    ) -> None:
        values = (
            reserve_bytes,
            reserve_files,
            stale_grace_seconds,
            stale_charge_bytes,
            stale_charge_files,
        )
        optional_reserves = (stale_reserve_bytes, stale_reserve_files)
        if any(value < 0 for value in values) or any(
            value is not None and value < 0 for value in optional_reserves
        ):
            raise ValueError("quota reserves must be nonnegative")
        if stale_grace_seconds and (stale_charge_bytes <= 0 or stale_charge_files <= 0):
            raise ValueError("stale quota grace requires positive pessimistic charges")
        self.status_path = status_path
        self.reserve_bytes = reserve_bytes
        self.reserve_files = reserve_files
        self.stale_grace_seconds = stale_grace_seconds
        self.stale_charge_bytes = stale_charge_bytes
        self.stale_charge_files = stale_charge_files
        self.stale_reserve_bytes = max(
            reserve_bytes,
            reserve_bytes if stale_reserve_bytes is None else stale_reserve_bytes,
        )
        self.stale_reserve_files = max(
            reserve_files,
            reserve_files if stale_reserve_files is None else stale_reserve_files,
        )
        self.lock = threading.Lock()
        self.checked_at = 0.0
        self.bound = 0
        self.file_bound = 0
        self.quota: PersonalQuota | None = None
        self.stale_failures = 0

    def _record(self, *, source: str, error: str | None = None) -> None:
        """Persist the storage bound and evidence source, without participant data."""
        assert self.quota is not None
        value = {
            "checked_utc": utc_now(),
            "quota": self.quota.__dict__,
            "quota_source": source,
            "charged_bound_bytes": self.bound,
            "charged_bound_files": self.file_bound,
            "reserve_bytes": self.reserve_bytes,
            "reserve_files": self.reserve_files,
            "stale_reserve_bytes": self.stale_reserve_bytes,
            "stale_reserve_files": self.stale_reserve_files,
            "stale_failures": self.stale_failures,
        }
        if error:
            value["quota_error"] = error
            value["stale_age_seconds"] = max(0.0, time.monotonic() - self.checked_at)
        atomic_write_json(self.status_path, value)

    def _require_headroom(self, incoming_bytes: int, *, stale: bool) -> None:
        """Enforce byte and inode reserves against fresh or pessimistic stale bounds."""
        assert self.quota is not None
        reserve_bytes = self.stale_reserve_bytes if stale else self.reserve_bytes
        reserve_files = self.stale_reserve_files if stale else self.reserve_files
        if (
            self.bound + incoming_bytes > self.quota.limit_bytes - reserve_bytes
            or self.file_bound > self.quota.limit_files - reserve_files
        ):
            mode = "bounded stale quota" if stale else "personal scratch quota"
            raise CapacityError(f"{mode} reserve reached; partial outputs retained")

    def __call__(self, incoming_bytes: int) -> None:
        """Check/charge an imminent write, with optional bounded stale-service grace.

        Default callers remain fail-closed. A long-running compute caller may opt into
        grace only after a successful fresh reading. Every unavailable refresh then
        charges declared worst-case bytes/files and uses stricter reserves until a
        fresh personal counter is obtained; shared filesystem capacity is never used.
        """
        if incoming_bytes < 0:
            raise ValueError("incoming bytes must be nonnegative")
        with self.lock:
            if self.quota is None or time.monotonic() - self.checked_at >= 60:
                try:
                    quota = read_personal_quota()
                except CapacityError as exc:
                    now = time.monotonic()
                    transient = str(exc).startswith("personal quota service unavailable")
                    if (
                        not transient
                        or self.quota is None
                        or self.stale_grace_seconds <= 0
                        or now - self.checked_at > self.stale_grace_seconds
                    ):
                        raise
                    self.stale_failures += 1
                    self.bound += self.stale_charge_bytes
                    self.file_bound += self.stale_charge_files
                    self._record(source="bounded_stale", error=str(exc))
                    self._require_headroom(incoming_bytes, stale=True)
                    self.bound += incoming_bytes
                    return
                self.quota = quota
                self.checked_at = time.monotonic()
                self.bound = max(self.bound, quota.used_bytes)
                self.file_bound = max(self.file_bound, quota.used_files)
                self.stale_failures = 0
                self._record(source="fresh")
            self._require_headroom(incoming_bytes, stale=False)
            self.bound += incoming_bytes


def scratch_environment(root: Path) -> dict[str, str]:
    """Return cache/temp destinations beneath a validated fresh personal run, no writes."""
    validate_fresh_root(root, check_host=False)
    return {
        "TMPDIR": str(root / "tmp"),
        "PIP_CACHE_DIR": str(root / "cache/pip"),
        "XDG_CACHE_HOME": str(root / "cache/xdg"),
        "HF_HOME": str(root / "cache/huggingface"),
        "HF_HUB_CACHE": str(root / "cache/huggingface/hub"),
        "HF_XET_CACHE": str(root / "cache/huggingface/xet"),
        "MPLCONFIGDIR": str(root / "cache/matplotlib"),
        "NILEARN_DATA": str(root / "cache/nilearn"),
    }
