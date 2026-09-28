"""Read-only, compute-node census of this study's scratch directory entries.

This counts path entries without following symlinks. Hard-linked paths count
separately, so the number is an inventory measure, not a replacement for the
personal Lustre inode quota reported by ``diskusage_report``.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

STUDY_ROOT = Path("/scratch/pwa209/cognition-and-consciousness")
FOCUSES = {
    "project": STUDY_ROOT,
    "masked-neural": STUDY_ROOT / "fresh-20260916/analysis/masked-neural",
    "raw": STUDY_ROOT / "fresh-20260916/data/raw",
}


def census(root: Path) -> dict[str, object]:
    """Return non-followed entry counts by the first three directory levels."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("study root must be a real directory")
    counts: Counter[str] = Counter()
    total = 1  # root directory itself
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = Path(entry.path).relative_to(root)
                parts = relative.parts
                total += 1
                for depth in range(1, min(len(parts), 3) + 1):
                    counts["/".join(parts[:depth])] += 1
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
    return {
        "root": str(root),
        "entries_including_root": total,
        "by_prefix": dict(sorted(counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--focus", choices=tuple(FOCUSES), default="project")
    args = parser.parse_args()
    print(json.dumps(census(FOCUSES[args.focus]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
