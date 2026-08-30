from __future__ import annotations

from pathlib import Path

from factorcon.config import DatasetConfig
from factorcon.pipeline.harmonize import harmonize_multisite_working_memory


def test_working_memory_clean_table_mapping(tmp_path: Path) -> None:
    source = tmp_path / "Data" / "uWM_012_Clean_Data.csv"
    source.parent.mkdir()
    source.write_text(
        "laboratory,participant,subjID,session,block,trial,phase,cueType,oriMemo,gyre,oriTest,contrast,WMresp,WMacc,PASresp,language,payment,age,gender\n"
        "1,1,1,1,1,1,experiment,1,20,1,25,0.05,1,1,2,English,credits,20,F\n"
        "2,1,2,1,1,1,experiment,0,20,-1,15,0.05,0,0,1,German,money,21,M\n",
        encoding="utf-8",
    )
    config = DatasetConfig(
        Path("fixture.yaml"),
        {
            "family": "multisite_working_memory",
            "source_type": "osf",
            "source_id": "fixture",
            "access": "public",
            "modalities": ["behavior"],
            "expected_participants": 2,
            "expected_sites": 2,
        },
    )
    records, report = harmonize_multisite_working_memory(config, tmp_path)
    assert report["participants"] == 2
    assert records[0].observed_experience == 2.0
    assert records[0].stimulus_features["cue_type"] == 1.0
    assert records[1].condition == "experiment:cue_absent"
