"""Garment template output contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TEMPLATE_FILES = {
    "tshirt": ("tshirt.glb", "uv-layout.png", "anchors.json"),
    "pants": ("pants.glb", "uv-layout.png", "anchors.json"),
}

COMMON_TOP_LEVEL_FIELDS = (
    "category",
    "coordinate_system",
    "version",
    "uv_regions",
    "anchors",
    "vertex_groups",
    "scale_regions",
    "default_allowance",
)

REQUIRED_FIELDS_BY_CATEGORY = {
    "tshirt": {
        "uv_regions": ("front", "back", "left_sleeve", "right_sleeve"),
        "anchors": (
            "left_shoulder",
            "right_shoulder",
            "neck",
            "left_sleeve_opening",
            "right_sleeve_opening",
            "hem_center",
        ),
        "vertex_groups": ("shoulders", "torso", "left_sleeve", "right_sleeve"),
        "scale_regions": ("shoulder_width", "chest_width", "shirt_length"),
    },
    "pants": {
        "uv_regions": ("front", "back", "left_leg", "right_leg"),
        "anchors": ("waist_center", "hip_center", "left_hem", "right_hem"),
        "vertex_groups": ("waist", "hip", "left_leg", "right_leg"),
        "scale_regions": ("waist_width", "hip_width", "leg_length", "hem_width"),
    },
}


class GarmentTemplateContractError(ValueError):
    """Raised when a garment template directory is invalid."""


def validate_garment_template(
    template_dir: str | Path,
    *,
    category: str,
) -> dict[str, Any]:
    """Validate one garment template directory."""

    if category not in REQUIRED_TEMPLATE_FILES:
        raise GarmentTemplateContractError(f"Unknown garment category: {category}")

    root = Path(template_dir)
    missing = [name for name in REQUIRED_TEMPLATE_FILES[category] if not (root / name).is_file()]
    if missing:
        raise GarmentTemplateContractError(
            f"Missing garment template file(s) under {root}: {', '.join(missing)}"
        )

    with (root / f"{category}.glb").open("rb") as file:
        if file.read(4) != b"glTF":
            raise GarmentTemplateContractError(
                f"{root / f'{category}.glb'} is not a binary glTF/GLB file"
            )
    with (root / "uv-layout.png").open("rb") as file:
        if file.read(8) != b"\x89PNG\r\n\x1a\n":
            raise GarmentTemplateContractError(f"{root / 'uv-layout.png'} is not a PNG")

    metadata = _read_json(root / "anchors.json")
    _validate_metadata(metadata, category, root / "anchors.json")
    return {
        "root": str(root),
        "category": category,
        "mesh": str(root / f"{category}.glb"),
        "uv_layout": str(root / "uv-layout.png"),
        "metadata": metadata,
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise GarmentTemplateContractError(f"{path} must contain a JSON object")
    return data


def _validate_metadata(data: dict[str, Any], category: str, path: Path) -> None:
    for field in COMMON_TOP_LEVEL_FIELDS:
        if field not in data:
            raise GarmentTemplateContractError(f"{path}: missing {field}")
    if data["category"] != category:
        raise GarmentTemplateContractError(
            f"{path}: category must be {category!r}, got {data['category']!r}"
        )
    if data["coordinate_system"] != "template_local":
        raise GarmentTemplateContractError(
            f"{path}: coordinate_system must be 'template_local'"
        )
    if not isinstance(data["version"], int) or data["version"] < 1:
        raise GarmentTemplateContractError(f"{path}: version must be a positive integer")

    for section in ("uv_regions", "anchors", "vertex_groups", "scale_regions", "default_allowance"):
        if not isinstance(data[section], dict):
            raise GarmentTemplateContractError(f"{path}: {section} must be an object")

    required = REQUIRED_FIELDS_BY_CATEGORY[category]
    for section, keys in required.items():
        missing = [key for key in keys if key not in data[section]]
        if missing:
            raise GarmentTemplateContractError(
                f"{path}: {section} missing key(s): {', '.join(missing)}"
            )

    for name, region in data["uv_regions"].items():
        _validate_uv_region(region, f"{path}: uv_regions.{name}")
    for name, anchor in data["anchors"].items():
        if not _is_vec3(anchor):
            raise GarmentTemplateContractError(
                f"{path}: anchors.{name} must be a numeric [x, y, z] vector"
            )
    for name, group in data["vertex_groups"].items():
        if not isinstance(group, list) or not group or not all(isinstance(item, int) for item in group):
            raise GarmentTemplateContractError(
                f"{path}: vertex_groups.{name} must be a non-empty integer list"
            )
    for name, region in data["scale_regions"].items():
        if not isinstance(region, dict):
            raise GarmentTemplateContractError(
                f"{path}: scale_regions.{name} must be an object"
            )
        if not isinstance(region.get("vertex_group"), str):
            raise GarmentTemplateContractError(
                f"{path}: scale_regions.{name}.vertex_group must be a string"
            )


def _validate_uv_region(region: Any, label: str) -> None:
    if not isinstance(region, dict):
        raise GarmentTemplateContractError(f"{label} must be an object")
    values = []
    for field in ("u_min", "v_min", "u_max", "v_max"):
        value = region.get(field)
        if not isinstance(value, (int, float)):
            raise GarmentTemplateContractError(f"{label}.{field} must be numeric")
        if not 0 <= float(value) <= 1:
            raise GarmentTemplateContractError(f"{label}.{field} must be between 0 and 1")
        values.append(float(value))
    u_min, v_min, u_max, v_max = values
    if u_min >= u_max or v_min >= v_max:
        raise GarmentTemplateContractError(f"{label} min values must be smaller than max values")


def _is_vec3(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(item, (int, float)) for item in value)
    )
