"""Synthetic COGITATE Exp1 fMRI schema, count and confinement tests."""

import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.cogitate_events import harmonize_cogitate_fmri, parse_fmri_events
from factorcon.util import read_jsonl

MEMBER = "BIDS/sub-XX001/ses-1/func/sub-XX001_ses-1_task-Dur_run-1_events.tsv"
PAYLOAD = (
    b"onset\tduration\ttrial_type\ttask_relevance\tstimulus_orientation\tstimulus_id\tresponse\n"
    b"0\t0.5\tface\trelevant\tcenter\t1101\tcorrectRejection\n"
    b"2\t0\tresponse\tresponse\tResponse\tresponse\thit\n"
)


def test_parser_preserves_distinctions():
    records = parse_fmri_events(PAYLOAD, MEMBER, "fixture.zip")
    assert len(records) == 2
    assert records[0].observed_experience is None
    assert records[0].response is None  # correct rejection is not a button event
    assert records[0].metadata["behavioral_outcome"] == "correctRejection"
    assert records[1].metadata["event_role"] == "response"
    assert records[0].stimulus_features["task_relevance"] == "relevant"
    assert records[0].subject == records[1].subject == "XX001"


@pytest.mark.parametrize(
    "payload",
    [
        PAYLOAD.replace(b"center", b"unknown"),
        PAYLOAD.replace(b"relevant", b"newlevel"),
        PAYLOAD.replace(b"0.5", b"nan"),
        PAYLOAD.replace(b"2\t0", b"-2\t0"),
        PAYLOAD.replace(b"stimulus_id", b"unknown_id"),
    ],
)
def test_unverified_schema_levels_timing_rejected(payload):
    with pytest.raises((IntegrityError, ValueError)):
        parse_fmri_events(payload, MEMBER, "fixture.zip")


def test_traversal_rejected_and_cell_paths_never_followed():
    with pytest.raises(IntegrityError):
        parse_fmri_events(PAYLOAD, "../" + MEMBER, "fixture.zip")
    records = parse_fmri_events(
        PAYLOAD.replace(b"1101", b"../../not_opened"), MEMBER, "fixture.zip"
    )
    assert records[0].stimulus_id == "../../not_opened"


def test_archive_counts_and_jsonl(tmp_path):
    name = "fixture_bids_fmri_archive.zip"
    with zipfile.ZipFile(tmp_path / name, "w") as z:
        z.writestr(MEMBER, PAYLOAD)
    inputs = SimpleNamespace(data_root=tmp_path, records=[SimpleNamespace(relative_path=name)])
    result = harmonize_cogitate_fmri(
        inputs, tmp_path / "trials.jsonl", expected_participants=1, expected_event_files=1
    )
    assert result["participants"] == 1 and result["records"] == 2
    assert len(list(read_jsonl(tmp_path / "trials.jsonl"))) == 2
    with pytest.raises(IntegrityError, match="event-file count"):
        harmonize_cogitate_fmri(
            inputs, tmp_path / "bad.jsonl", expected_participants=1, expected_event_files=2
        )
    with pytest.raises(IntegrityError, match="participant count"):
        harmonize_cogitate_fmri(
            inputs, tmp_path / "bad.jsonl", expected_participants=2, expected_event_files=1
        )
    assert not (tmp_path / "bad.jsonl").exists()


def test_archive_resolution_escape(tmp_path, monkeypatch):
    name = "fixture_bids_fmri_archive.zip"
    path = tmp_path / name
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda p, *a, **kw: tmp_path.parent / "outside" if p == path else original(p, *a, **kw),
    )
    inputs = SimpleNamespace(data_root=tmp_path, records=[SimpleNamespace(relative_path=name)])
    with pytest.raises(IntegrityError, match="escapes"):
        harmonize_cogitate_fmri(
            inputs, tmp_path / "trials.jsonl", expected_participants=1, expected_event_files=1
        )
