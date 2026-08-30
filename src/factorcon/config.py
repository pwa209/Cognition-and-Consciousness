"""Declarative project configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factorcon.errors import ConfigError
from factorcon.util import load_structured


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    """Validated dataset acquisition and analysis metadata."""

    path: Path
    values: dict[str, Any]

    @property
    def family(self) -> str:
        return str(self.values["family"])

    @property
    def source_type(self) -> str:
        return str(self.values["source_type"])

    @property
    def access(self) -> str:
        return str(self.values["access"])

    @property
    def snapshot_label(self) -> str:
        return str(
            self.values.get("snapshot")
            or self.values.get("snapshot_label")
            or self.values.get("registry_version")
            or "unversioned"
        )


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Resolved top-level configuration with linked dataset and server records."""

    path: Path
    root: Path
    values: dict[str, Any]
    server: dict[str, Any]
    analysis_spec: dict[str, Any]
    datasets: tuple[DatasetConfig, ...]
    construct_maps: tuple[dict[str, Any], ...]

    @property
    def canonical_root(self) -> Path:
        return Path(str(self.server["canonical_root"]))

    @property
    def fast_root(self) -> Path:
        return Path(str(self.server["fast_root"]))

    @property
    def restart_root(self) -> Path:
        return Path(str(self.server["restart_root"]))

    @property
    def random_seed(self) -> int:
        return int(self.values["random_seed"])


def _resolve(project_root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else project_root / candidate


def _require(mapping: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - mapping.keys())
    if missing:
        raise ConfigError(f"{label} is missing required fields: {', '.join(missing)}")


def load_project(path: str | Path) -> ProjectConfig:
    """Load and cross-validate the project configuration graph."""

    config_path = Path(path).resolve()
    values = load_structured(config_path)
    _require(
        values,
        {"schema_version", "project", "analysis_spec", "server", "datasets", "construct_maps"},
        str(config_path),
    )
    root = config_path.parent.parent
    server_path = _resolve(root, str(values["server"]))
    analysis_path = _resolve(root, str(values["analysis_spec"]))
    server = load_structured(server_path)
    analysis = load_structured(analysis_path)
    _require(
        server,
        {"expected_hostname", "expected_user", "canonical_root", "fast_root", "restart_root"},
        str(server_path),
    )
    if analysis.get("registration") is not None:
        raise ConfigError("Project contract requires registration=null")
    if analysis.get("scientific_gates") is not False:
        raise ConfigError("Project contract requires scientific_gates=false")
    if analysis.get("report_all_candidate_models") is not True:
        raise ConfigError("All candidate models must be reported")

    dataset_records: list[DatasetConfig] = []
    seen_families: set[str] = set()
    for item in values["datasets"]:
        dataset_path = _resolve(root, str(item))
        dataset = load_structured(dataset_path)
        _require(
            dataset,
            {"schema_version", "family", "source_type", "source_id", "access", "modalities"},
            str(dataset_path),
        )
        family = str(dataset["family"])
        if family in seen_families:
            raise ConfigError(f"Duplicate dataset family: {family}")
        seen_families.add(family)
        dataset_records.append(DatasetConfig(dataset_path, dataset))

    maps: list[dict[str, Any]] = []
    map_families: set[str] = set()
    for item in values["construct_maps"]:
        map_path = _resolve(root, str(item))
        construct_map = load_structured(map_path)
        _require(construct_map, {"schema_version", "family", "mappings", "contrasts"}, str(map_path))
        family = str(construct_map["family"])
        if family in map_families:
            raise ConfigError(f"Duplicate construct map: {family}")
        map_families.add(family)
        for index, mapping in enumerate(construct_map["mappings"]):
            if not isinstance(mapping, dict):
                raise ConfigError(f"{map_path}: mapping {index} is not an object")
            _require(
                mapping,
                {"observed", "construct", "direction", "scale", "uncertainty", "held_constant", "alternative", "enters"},
                f"{map_path}:mapping[{index}]",
            )
        maps.append(construct_map)
    if seen_families != map_families:
        raise ConfigError(
            f"Dataset/construct-map family mismatch: datasets={sorted(seen_families)}, maps={sorted(map_families)}"
        )

    candidate_models = tuple(values.get("candidate_models", ()))
    if candidate_models != ("M0", "M1", "M2", "M3", "M4", "M5"):
        raise ConfigError("candidate_models must list M0 through M5 exactly once in order")
    return ProjectConfig(
        path=config_path,
        root=root,
        values=values,
        server=server,
        analysis_spec=analysis,
        datasets=tuple(dataset_records),
        construct_maps=tuple(maps),
    )


def validate_project(path: str | Path) -> dict[str, Any]:
    """Return a machine-readable validation summary or raise ``ConfigError``."""

    project = load_project(path)
    return {
        "valid": True,
        "project": project.values["project"],
        "study_status": project.analysis_spec["study_status"],
        "registration": project.analysis_spec["registration"],
        "scientific_gates": project.analysis_spec["scientific_gates"],
        "dataset_families": [item.family for item in project.datasets],
        "candidate_models": list(project.values["candidate_models"]),
        "roots_status": project.server.get("roots_status"),
    }

