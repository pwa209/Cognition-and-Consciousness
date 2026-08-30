from __future__ import annotations

from pathlib import Path

import pytest

from factorcon.errors import IntegrityError
from factorcon.util import ensure_within, safe_relative_path


@pytest.mark.parametrize(
    "value",
    ["../secret", "a/../../secret", "/absolute/file", r"C:\\secret", r"..\\secret", ""],
)
def test_unsafe_upstream_paths_are_rejected(value: str) -> None:
    with pytest.raises(IntegrityError):
        safe_relative_path(value)


def test_safe_path_and_root_confinement(tmp_path: Path) -> None:
    relative = safe_relative_path("sub-01/func/events.tsv")
    assert relative == Path("sub-01") / "func" / "events.tsv"
    assert ensure_within(tmp_path, tmp_path / relative).is_relative_to(tmp_path.resolve())

