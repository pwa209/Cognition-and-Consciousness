"""Rorqual-only fresh-run identity and personal scratch quota boundaries.

All measurements below concern storage bytes/files, not participant outcomes. No
shared project path is accepted as a download/cache target. Scratch is not archival.
"""

from __future__ import annotations

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

        if pwd.getpwuid(os.getuid()).pw_name != "pwa209" or not socket.gethostname().startswith(
            "rorqual"
        ):
            raise IntegrityError("Rorqual/pwa209 identity required")
        if not PERSONAL_ROOT.is_dir() or path.resolve() != path:
            raise IntegrityError("missing personal scratch mount or redirected study path")
        if PERSONAL_ROOT.stat().st_uid != os.getuid():
            raise IntegrityError("personal scratch root is not owned by current user")
    return path


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
        r"/scratch\s+\(user pwa209\)\s+([\d.]+)\s*(B|KB|MB|GB|TB)\s*/\s*"
        r"([\d.]+)\s*(B|KB|MB|GB|TB)\s+([\d.]+)\s*([KMG]?)\s*/\s*([\d.]+)\s*([KMG]?)"
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
    """Read fresh quota counters without downloading data or changing storage."""
    command = subprocess.run(["diskusage_report"], capture_output=True, text=True, timeout=45)
    if command.returncode:
        raise CapacityError(
            "diskusage_report failed; download paused rather than assuming free space"
        )
    return parse_personal_quota(command.stdout)


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
    ) -> None:
        if reserve_bytes < 0 or reserve_files < 0:
            raise ValueError("quota reserves must be nonnegative")
        self.status_path = status_path
        self.reserve_bytes = reserve_bytes
        self.reserve_files = reserve_files
        self.lock = threading.Lock()
        self.checked_at = 0.0
        self.bound = 0
        self.quota: PersonalQuota | None = None

    def __call__(self, incoming_bytes: int) -> None:
        """Check/charge an imminent write in bytes; raise before exceeding the reserve."""
        if incoming_bytes < 0:
            raise ValueError("incoming bytes must be nonnegative")
        with self.lock:
            if self.quota is None or time.monotonic() - self.checked_at >= 60:
                self.quota = read_personal_quota()
                self.checked_at = time.monotonic()
                self.bound = max(self.bound, self.quota.used_bytes)
                atomic_write_json(
                    self.status_path,
                    {
                        "checked_utc": utc_now(),
                        "quota": self.quota.__dict__,
                        "charged_bound_bytes": self.bound,
                        "reserve_bytes": self.reserve_bytes,
                        "reserve_files": self.reserve_files,
                    },
                )
            if (
                self.bound + incoming_bytes > self.quota.limit_bytes - self.reserve_bytes
                or self.quota.used_files > self.quota.limit_files - self.reserve_files
            ):
                raise CapacityError(
                    "personal scratch quota reserve reached; partial downloads retained"
                )
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
