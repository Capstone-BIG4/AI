"""Garment image cleanup and texture atlas helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps, ImageStat

from backend.app.contracts.garment_texture import validate_garment_textures


DEFAULT_TEXTURE_SIZE = 1024


@dataclass(frozen=True)
class GarmentImageInputs:
    top_front: Path
    pants_front: Path
    top_back: Path | None = None
    pants_back: Path | None = None


def generate_garment_textures(
    inputs: GarmentImageInputs,
    output_dir: str | Path,
    *,
    texture_size: int = DEFAULT_TEXTURE_SIZE,
) -> dict[str, Any]:
    """Normalize uploaded garment product images into the texture contract."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    top_front = normalize_garment_image(
        inputs.top_front,
        root / "top_front.png",
        texture_size=texture_size,
        label="top_front",
    )
    top_back_estimated = inputs.top_back is None
    if inputs.top_back is None:
        top_back = copy_estimated_back_texture(root / "top_front.png", root / "top_back.png")
    else:
        top_back = normalize_garment_image(
            inputs.top_back,
            root / "top_back.png",
            texture_size=texture_size,
            label="top_back",
        )

    pants_front = normalize_garment_image(
        inputs.pants_front,
        root / "pants_front.png",
        texture_size=texture_size,
        label="pants_front",
    )
    pants_back_estimated = inputs.pants_back is None
    if inputs.pants_back is None:
        pants_back = copy_estimated_back_texture(
            root / "pants_front.png",
            root / "pants_back.png",
        )
    else:
        pants_back = normalize_garment_image(
            inputs.pants_back,
            root / "pants_back.png",
            texture_size=texture_size,
            label="pants_back",
        )

    quality = {
        "top": _quality_section(top_front, top_back, top_back_estimated),
        "pants": _quality_section(pants_front, pants_back, pants_back_estimated),
    }
    with (root / "garment_quality.json").open("w", encoding="utf-8") as file:
        json.dump(quality, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return validate_garment_textures(root)


def normalize_garment_image(
    source: str | Path,
    destination: str | Path,
    *,
    texture_size: int = DEFAULT_TEXTURE_SIZE,
    label: str,
) -> dict[str, Any]:
    """Crop garment area and place it on a square transparent canvas."""

    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    image = Image.open(source_path).convert("RGBA")
    crop_box, mask_kind, confidence = _find_garment_bbox(image)
    warnings: list[str] = []

    if crop_box is None:
        crop_box = (0, 0, image.width, image.height)
        mask_kind = "full_image"
        confidence = 0.25
        warnings.append("low_garment_mask_confidence")
    else:
        crop_box = _expand_box(crop_box, image.size, padding_ratio=0.045)
        if _touches_edge(crop_box, image.size):
            warnings.append("possible_garment_crop")

    cropped = _apply_background_cleanup(image.crop(crop_box), mask_kind)
    aspect_ratio = cropped.width / max(cropped.height, 1)
    if aspect_ratio < 0.25 or aspect_ratio > 1.3:
        warnings.append("unusual_garment_aspect_ratio")

    output = Image.new("RGBA", (texture_size, texture_size), (0, 0, 0, 0))
    margin = max(int(texture_size * 0.06), 1)
    max_width = texture_size - margin * 2
    max_height = texture_size - margin * 2
    scale = min(max_width / cropped.width, max_height / cropped.height)
    resized_size = (
        max(int(round(cropped.width * scale)), 1),
        max(int(round(cropped.height * scale)), 1),
    )
    resized = cropped.resize(resized_size, Image.Resampling.LANCZOS)
    offset = (
        (texture_size - resized.width) // 2,
        (texture_size - resized.height) // 2,
    )
    output.alpha_composite(resized, offset)

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination_path)

    return {
        "label": label,
        "source": str(source_path),
        "output": str(destination_path),
        "original_size": [image.width, image.height],
        "crop_box": list(crop_box),
        "mask_kind": mask_kind,
        "mask_confidence": round(confidence, 3),
        "warnings": warnings,
    }


def copy_estimated_back_texture(front_texture: str | Path, destination: str | Path) -> dict[str, Any]:
    """Create a simple back-side fallback from the normalized front texture."""

    image = Image.open(front_texture).convert("RGBA")
    output = ImageOps.mirror(image)
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination_path)
    return {
        "label": destination_path.stem,
        "source": str(front_texture),
        "output": str(destination_path),
        "original_size": [image.width, image.height],
        "crop_box": [0, 0, image.width, image.height],
        "mask_kind": "estimated_from_front",
        "mask_confidence": 0.45,
        "warnings": ["back_texture_estimated"],
    }


def build_texture_atlas(
    front_texture: str | Path,
    back_texture: str | Path,
    output_path: str | Path,
    uv_regions: dict[str, dict[str, float]],
    *,
    size: int = DEFAULT_TEXTURE_SIZE,
) -> Path:
    """Pack normalized front/back garment textures into a template atlas."""

    front = Image.open(front_texture).convert("RGBA")
    back = Image.open(back_texture).convert("RGBA")
    average_color = _average_visible_color(front)
    atlas = Image.new("RGBA", (size, size), average_color)
    draw = ImageDraw.Draw(atlas, "RGBA")

    for name, region in uv_regions.items():
        box = _region_to_pixel_box(region, size)
        if name in ("front", "left_leg"):
            _paste_contained(atlas, front, box)
        elif name in ("back", "right_leg"):
            _paste_contained(atlas, back, box)
        elif "sleeve" in name:
            draw.rectangle(box, fill=average_color)
        else:
            draw.rectangle(box, fill=average_color)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(target)
    return target


def draw_uv_layout(
    output_path: str | Path,
    uv_regions: dict[str, dict[str, float]],
    *,
    size: int = DEFAULT_TEXTURE_SIZE,
) -> Path:
    """Write a simple UV layout image for template inspection."""

    image = Image.new("RGBA", (size, size), (30, 34, 36, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    colors = [
        (95, 154, 255, 130),
        (255, 190, 95, 130),
        (125, 215, 150, 130),
        (240, 110, 145, 130),
        (180, 140, 250, 130),
    ]
    for index, (name, region) in enumerate(uv_regions.items()):
        box = _region_to_pixel_box(region, size)
        draw.rectangle(box, fill=colors[index % len(colors)], outline=(255, 255, 255, 220), width=3)
        draw.text((box[0] + 10, box[1] + 10), name, fill=(255, 255, 255, 255))

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return target


def _find_garment_bbox(image: Image.Image) -> tuple[tuple[int, int, int, int] | None, str, float]:
    alpha = image.getchannel("A")
    alpha_min, _ = alpha.getextrema()
    if alpha_min < 250:
        alpha_bbox = alpha.point(lambda value: 255 if value > 12 else 0).getbbox()
        if alpha_bbox is not None:
            area_ratio = _box_area(alpha_bbox) / max(image.width * image.height, 1)
            if area_ratio < 0.96:
                confidence = 0.98 if area_ratio < 0.92 else 0.82
                return alpha_bbox, "alpha", confidence

    background = _corner_average_rgb(image)
    mask = Image.new("L", image.size, 0)
    pixels = image.convert("RGB").load()
    mask_pixels = mask.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = pixels[x, y]
            distance = abs(r - background[0]) + abs(g - background[1]) + abs(b - background[2])
            if distance > 42:
                mask_pixels[x, y] = 255
    bbox = mask.getbbox()
    if bbox is None:
        return None, "none", 0.0
    area_ratio = _box_area(bbox) / max(image.width * image.height, 1)
    confidence = 0.78 if 0.04 <= area_ratio <= 0.9 else 0.5
    return bbox, "background", confidence


def _apply_background_cleanup(image: Image.Image, mask_kind: str) -> Image.Image:
    if mask_kind != "background":
        return image
    background = _corner_average_rgb(image)
    result = image.copy()
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            r, g, b, alpha = pixels[x, y]
            distance = abs(r - background[0]) + abs(g - background[1]) + abs(b - background[2])
            if distance <= 42:
                pixels[x, y] = (r, g, b, 0)
            else:
                pixels[x, y] = (r, g, b, alpha)
    return result


def _quality_section(
    front: dict[str, Any],
    back: dict[str, Any],
    back_estimated: bool,
) -> dict[str, Any]:
    warnings = [*front["warnings"], *back["warnings"]]
    if back_estimated and "back_texture_estimated" not in warnings:
        warnings.append("back_texture_estimated")
    return {
        "front_mask_confidence": front["mask_confidence"],
        "back_mask_confidence": back["mask_confidence"],
        "back_estimated": back_estimated,
        "warnings": sorted(set(warnings)),
        "front": front,
        "back": back,
    }


def _expand_box(
    box: tuple[int, int, int, int],
    size: tuple[int, int],
    *,
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    pad_x = int(round(width * padding_ratio))
    pad_y = int(round(height * padding_ratio))
    return (
        max(left - pad_x, 0),
        max(top - pad_y, 0),
        min(right + pad_x, size[0]),
        min(bottom + pad_y, size[1]),
    )


def _touches_edge(box: tuple[int, int, int, int], size: tuple[int, int]) -> bool:
    return box[0] <= 1 or box[1] <= 1 or box[2] >= size[0] - 1 or box[3] >= size[1] - 1


def _box_area(box: tuple[int, int, int, int]) -> int:
    return max(box[2] - box[0], 0) * max(box[3] - box[1], 0)


def _corner_average_rgb(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    samples = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    return tuple(sum(color[channel] for color in samples) // len(samples) for channel in range(3))


def _average_visible_color(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 12 else 0).getbbox()
    if bbox is None:
        return (180, 180, 180, 255)
    cropped = image.crop(bbox)
    visible = Image.new("RGBA", cropped.size, (0, 0, 0, 0))
    visible.alpha_composite(cropped)
    stat = ImageStat.Stat(visible, visible.getchannel("A"))
    r, g, b, _ = [int(value) for value in stat.mean]
    return (r, g, b, 255)


def _region_to_pixel_box(region: dict[str, float], size: int) -> tuple[int, int, int, int]:
    return (
        int(round(region["u_min"] * size)),
        int(round(region["v_min"] * size)),
        int(round(region["u_max"] * size)),
        int(round(region["v_max"] * size)),
    )


def _paste_contained(
    target: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    width = max(right - left, 1)
    height = max(bottom - top, 1)
    scale = min(width / source.width, height / source.height)
    resized = source.resize(
        (
            max(int(round(source.width * scale)), 1),
            max(int(round(source.height * scale)), 1),
        ),
        Image.Resampling.LANCZOS,
    )
    offset = (
        left + (width - resized.width) // 2,
        top + (height - resized.height) // 2,
    )
    target.alpha_composite(resized, offset)
