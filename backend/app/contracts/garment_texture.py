"""Garment texture output contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TEXTURE_FILES = (
    "top_front.png",
    "top_back.png",
    "pants_front.png",
    "pants_back.png",
    "garment_quality.json",
)


class GarmentTextureContractError(ValueError):
    """Raised when generated garment textures are invalid."""


def validate_garment_textures(output_dir: str | Path) -> dict[str, Any]:
    """Validate generated garment texture files and quality metadata."""

    root = Path(output_dir)
    missing = [name for name in REQUIRED_TEXTURE_FILES if not (root / name).is_file()]
    if missing:
        raise GarmentTextureContractError(
            f"Missing garment texture file(s) under {root}: {', '.join(missing)}"
        )
    for name in REQUIRED_TEXTURE_FILES[:-1]:
        with (root / name).open("rb") as file:
            if file.read(8) != b"\x89PNG\r\n\x1a\n":
                raise GarmentTextureContractError(f"{root / name} is not a PNG")

    quality = _read_json(root / "garment_quality.json")
    for section in ("top", "pants"):
        if not isinstance(quality.get(section), dict):
            raise GarmentTextureContractError(
                f"{root / 'garment_quality.json'}: {section} must be an object"
            )
        _validate_quality_section(quality[section], section, root / "garment_quality.json")

    return {
        "root": str(root),
        "textures": {name: str(root / name) for name in REQUIRED_TEXTURE_FILES[:-1]},
        "quality": quality,
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise GarmentTextureContractError(f"{path} must contain a JSON object")
    return data


def _validate_quality_section(data: dict[str, Any], section: str, path: Path) -> None:
    for field in ("front_mask_confidence", "back_mask_confidence"):
        value = data.get(field)
        if not isinstance(value, (int, float)):
            raise GarmentTextureContractError(f"{path}: {section}.{field} must be numeric")
        if not 0 <= float(value) <= 1:
            raise GarmentTextureContractError(
                f"{path}: {section}.{field} must be between 0 and 1"
            )
    if not isinstance(data.get("back_estimated"), bool):
        raise GarmentTextureContractError(f"{path}: {section}.back_estimated must be boolean")
    if not isinstance(data.get("warnings"), list):
        raise GarmentTextureContractError(f"{path}: {section}.warnings must be a list")
