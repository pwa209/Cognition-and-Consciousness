"""Independent behavioral-log/CSV timing checks for BMVP report MRI runs."""

from __future__ import annotations

import csv
import io
import math
import re
import statistics
from dataclasses import dataclass

from factorcon.errors import IntegrityError


_TRIGGER = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s+DATA\s+Keypress: 5\s*$")


@dataclass(frozen=True, slots=True)
class BmvpRunTiming:
    """One report run; times are seconds on the behavioral clock, no neural fit."""

    block: int
    first_trigger_seconds: float
    first_trial_seconds: float
    first_trial_onset_seconds: float
    task_trials: int
    trigger_count: int
    median_trigger_interval_seconds: float
    max_trigger_interval_seconds: float


def align_report_mri_timing(
    log_bytes: bytes,
    csv_bytes: bytes,
    *,
    expected_runs: int = 4,
    expected_volumes_per_run: int = 720,
    expected_task_trials_per_run: int = 32,
    tr_seconds: float = 1.0,
    expected_pretrial_triggers: int = 10,
) -> tuple[BmvpRunTiming, ...]:
    """Link report-MRI task blocks to scanner trigger trains, in seconds.

    The only inputs are the original PsychoPy log and behavioral CSV, not BOLD
    signals or fitted outcomes. A 1:1 trigger/converted-volume correspondence
    must also be verified externally for each DICOM series. This function never
    selects runs by neural score and makes no E or cross-family calibration.
    """
    if (
        expected_runs < 1
        or expected_volumes_per_run < 2
        or expected_task_trials_per_run < 1
        or not math.isfinite(tr_seconds)
        or tr_seconds <= 0
        or expected_pretrial_triggers < 0
        or expected_pretrial_triggers >= expected_volumes_per_run - 1
    ):
        raise ValueError("invalid timing expectations")
    try:
        log_text = log_bytes.decode("utf-8-sig")
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeError as exc:
        raise IntegrityError("BMVP timing files are not valid UTF-8") from exc
    triggers: list[float] = []
    for line in log_text.splitlines():
        match = _TRIGGER.fullmatch(line)
        if match:
            triggers.append(float(match.group(1)))
    if not triggers or any(b <= a for a, b in zip(triggers, triggers[1:])):
        raise IntegrityError("missing or nonmonotonic scanner triggers")
    trains: list[list[float]] = []
    for trigger in triggers:
        if not trains or trigger - trains[-1][-1] > 3 * tr_seconds:
            trains.append([])
        trains[-1].append(trigger)
    task_trains = [train for train in trains if len(train) == expected_volumes_per_run]
    if len(task_trains) != expected_runs:
        raise IntegrityError("task trigger-train count/volume count mismatch")
    for train in task_trains:
        gaps = [b - a for a, b in zip(train, train[1:])]
        if (
            abs(statistics.median(gaps) - tr_seconds) > 0.05 * tr_seconds
            or min(gaps) < 0.5 * tr_seconds
            or max(gaps) > 1.5 * tr_seconds
        ):
            raise IntegrityError("scanner trigger cadence is not compatible with TR")
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    required = {"TRIAL TYPE", "Trial start time", "BLOCK NUMBER"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise IntegrityError("report timing CSV lacks required fields")
    by_block: dict[int, list[float]] = {}
    for row in reader:
        trial_type = (row.get("TRIAL TYPE") or "").strip()
        if not trial_type or "CALIBRATION" in trial_type.upper():
            continue
        try:
            block = int((row.get("BLOCK NUMBER") or "").strip())
            onset = float((row.get("Trial start time") or "").strip())
        except ValueError as exc:
            raise IntegrityError("report task block/onset is not numeric") from exc
        if not math.isfinite(onset):
            raise IntegrityError("report task onset is not finite")
        by_block.setdefault(block, []).append(onset)
    if sorted(by_block) != list(range(1, expected_runs + 1)):
        raise IntegrityError("report task block identities are incomplete")
    results: list[BmvpRunTiming] = []
    for block, train in enumerate(task_trains, start=1):
        trials = by_block[block]
        if len(trials) != expected_task_trials_per_run or any(
            b <= a for a, b in zip(trials, trials[1:])
        ):
            raise IntegrityError("report task trial count/order mismatch")
        if any(t < train[0] or t >= train[0] + expected_volumes_per_run * tr_seconds for t in trials):
            raise IntegrityError("report task onset lies outside its scanner run")
        first_trial = trials[0]
        # The first task trial follows exactly the pretask trigger sequence;
        # require independent log/CSV agreement to within 100 ms.
        if (
            not train[expected_pretrial_triggers] <= first_trial < train[expected_pretrial_triggers + 1]
            or abs(first_trial - train[expected_pretrial_triggers]) > 0.1
        ):
            raise IntegrityError("report block does not align to expected trigger index")
        gaps = [b - a for a, b in zip(train, train[1:])]
        results.append(
            BmvpRunTiming(
                block=block,
                first_trigger_seconds=train[0],
                first_trial_seconds=first_trial,
                first_trial_onset_seconds=first_trial - train[0],
                task_trials=len(trials),
                trigger_count=len(train),
                median_trigger_interval_seconds=statistics.median(gaps),
                max_trigger_interval_seconds=max(gaps),
            )
        )
    return tuple(results)
