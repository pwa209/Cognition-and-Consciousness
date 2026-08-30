from __future__ import annotations

from pathlib import Path

from factorcon.config import load_project

ROOT = Path(__file__).resolve().parents[2]


def test_pinned_openneuro_identity_fields() -> None:
    project = load_project(ROOT / "conf" / "base.yaml")
    by_family = {dataset.family: dataset.values for dataset in project.datasets}
    expected = {
        "masked_content_fmri": ("ds003927", "1.0.3", "1f62eb63f0e55023609add6dd6148545b762b804"),
        "propofol_volition_fmri": ("ds006623", "1.0.0", "9c36d2c59d58fbbced4af6d0413d22a6ea5c4880"),
        "propofol_awakening_eeg": ("ds005620", "1.0.0", "a7ee50741b5625ee54478be73201ecfd4fd904dd"),
    }
    for family, identity in expected.items():
        value = by_family[family]
        assert (value["source_id"], value["snapshot"], value["git_sha"]) == identity


def test_access_control_is_not_misrepresented_as_public() -> None:
    project = load_project(ROOT / "conf" / "base.yaml")
    cogitate = next(item for item in project.datasets if item.family == "cogitate")
    assert cogitate.access == "account_and_terms_required"
    assert cogitate.values["requires_owner_action"] is True

