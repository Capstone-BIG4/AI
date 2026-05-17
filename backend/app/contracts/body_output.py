"""Body reconstruction output contract.

Phase 0 intentionally keeps this module dependency-free so the contract can be
validated before SAM 3D Body, PyTorch, or viewer dependencies are installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_BODY_FILES = ("body.glb", "landmarks.json", "body_metadata.json")

REQUIRED_LANDMARKS = (
    "neck",
    "left_shoulder",
    "right_shoulder",
    "chest_center",
    "waist_center",
    "hip_center",
    "left_wrist",
    "right_wrist",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


class BodyOutputContractError(ValueError):
    """Raised when a body output directory does not satisfy the contract."""


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise BodyOutputContractError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def validate_body_output(output_dir: str | Path) -> dict[str, Any]:
    """Validate a directory against the phase-0 body output contract."""

    root = Path(output_dir)
    missing = [name for name in REQUIRED_BODY_FILES if not (root / name).is_file()]
    if missing:
        raise BodyOutputContractError(
            f"Missing body output file(s) under {root}: {', '.join(missing)}"
        )

    body_path = root / "body.glb"
    with body_path.open("rb") as file:
        header = file.read(4)
    if header != b"glTF":
        raise BodyOutputContractError(f"{body_path} is not a binary glTF/GLB file")

    landmarks = read_json(root / "landmarks.json")
    metadata = read_json(root / "body_metadata.json")

    _validate_landmarks(landmarks, root / "landmarks.json")
    _validate_metadata(metadata, root / "body_metadata.json")

    return {
        "root": str(root),
        "body_glb": str(body_path),
        "landmarks": landmarks,
        "metadata": metadata,
    }


def _validate_landmarks(data: dict[str, Any], path: Path) -> None:
    coordinate_system = data.get("coordinate_system")
    if coordinate_system != "viewer":
        raise BodyOutputContractError(
            f"{path}: coordinate_system must be 'viewer', got {coordinate_system!r}"
        )

    points = data.get("points")
    if not isinstance(points, dict):
        raise BodyOutputContractError(f"{path}: points must be an object")

    missing = [name for name in REQUIRED_LANDMARKS if name not in points]
    if missing:
        raise BodyOutputContractError(
            f"{path}: missing landmark point(s): {', '.join(missing)}"
        )

    for name in REQUIRED_LANDMARKS:
        value = points[name]
        if not _is_vec3(value):
            raise BodyOutputContractError(
                f"{path}: landmark {name!r} must be a numeric [x, y, z] vector"
            )

    measurements = data.get("measurements_estimated")
    if not isinstance(measurements, dict):
        raise BodyOutputContractError(
            f"{path}: measurements_estimated must be an object"
        )


def _validate_metadata(data: dict[str, Any], path: Path) -> None:
    for field in ("job_id", "model_name", "model_version", "generated_at"):
        if not isinstance(data.get(field), str) or not data[field]:
            raise BodyOutputContractError(f"{path}: {field} must be a non-empty string")

    quality_score = data.get("quality_score")
    if not isinstance(quality_score, (int, float)):
        raise BodyOutputContractError(f"{path}: quality_score must be numeric")
    if not 0 <= float(quality_score) <= 1:
        raise BodyOutputContractError(f"{path}: quality_score must be between 0 and 1")

    warnings = data.get("warnings")
    if not isinstance(warnings, list):
        raise BodyOutputContractError(f"{path}: warnings must be a list")


def _is_vec3(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(item, (int, float)) for item in value)
    )
