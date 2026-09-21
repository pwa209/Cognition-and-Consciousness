"""Synthetic container regression: original failure and patched warning/plot/worker paths."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import multiprocessing
from pathlib import Path


def plot_check(output: str) -> dict[str, object]:
    """Exercise real warning handler and >20 figures; output is synthetic, no study data."""
    import fmriprep
    import fmriprep._warnings as handler
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import _api
    from matplotlib import pyplot as plt

    stream = io.StringIO()
    sink = logging.StreamHandler(stream)
    logger = logging.getLogger("py.warnings")
    logger.addHandler(sink)
    try:
        _api.warn_external("factorcon-warning-must-remain-visible", RuntimeWarning)
        for _ in range(22):
            plt.figure()
        plt.plot([0, 1], [0, 1])
        plt.savefig(output)
        message = stream.getvalue()
        if "factorcon-warning-must-remain-visible" not in message or "More than 20" not in message:
            raise ValueError("warning logging was suppressed")
        if not Path(output).stat().st_size:
            raise ValueError("synthetic plot missing")
        return {
            "status": "SUCCESS",
            "fmriprep_version": fmriprep.__version__,
            "warning_sha256": hashlib.sha256(Path(handler.__file__).read_bytes()).hexdigest(),
            "warnings_preserved": True,
            "synthetic_plot_bytes": Path(output).stat().st_size,
        }
    finally:
        plt.close("all")
        logger.removeHandler(sink)


def main() -> int:
    """Expect baseline TypeError, then require patched plots in parent and forkserver worker."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "patched"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.mode == "baseline":
        try:
            plot_check(str(args.output / "baseline.png"))
        except TypeError as exc:
            if "skip_file_prefixes" not in str(exc):
                raise
            print(json.dumps({"status": "EXPECTED_BASELINE_FAILURE", "error": str(exc)}))
            return 0
        raise ValueError("baseline unexpectedly passed; diagnosis needs review")
    result = plot_check(str(args.output / "parent.png"))
    with multiprocessing.get_context("forkserver").Pool(1) as pool:
        child = pool.apply_async(plot_check, (str(args.output / "child.png"),)).get(timeout=120)
    if child["warning_sha256"] != result["warning_sha256"]:
        raise ValueError("worker did not import identical patch")
    print(json.dumps({"parent": result, "forkserver_worker": child}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
