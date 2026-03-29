from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.config import ReconstructionSettings
from app.models import ManifestSample, ValidationMetrics, ValidationResult

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    cv2 = None


@dataclass(frozen=True)
class LoadedImage:
    image: Image.Image
    file_size_bytes: int


def load_image(path: Path) -> LoadedImage:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return LoadedImage(image=image, file_size_bytes=path.stat().st_size)


def resize_to_max_side(image: Image.Image, max_side: int) -> Image.Image:
    width, height = image.size
    longest_side = max(width, height)
    if longest_side <= max_side:
        return image.copy()

    scale = max_side / float(longest_side)
    resized = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    return resized


def center_crop_preview(image: Image.Image, crop_ratio: float) -> Image.Image:
    width, height = image.size
    crop_width = int(width * crop_ratio)
    crop_height = int(height * crop_ratio)
    left = max((width - crop_width) // 2, 0)
    top = max((height - crop_height) // 2, 0)
    return image.crop((left, top, left + crop_width, top + crop_height))


def brightness_mean(image: Image.Image) -> float:
    return float(np.asarray(image.convert("L"), dtype=np.float32).mean())


def blur_score(image: Image.Image) -> float:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    if cv2 is not None:
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    gray_f = gray.astype(np.float32)
    diff_x = np.abs(np.diff(gray_f, axis=1)).mean()
    diff_y = np.abs(np.diff(gray_f, axis=0)).mean()
    return float(diff_x + diff_y)


def portrait_bias(image: Image.Image) -> float:
    width, height = image.size
    return round(height / float(max(width, 1)), 4)


def _merge_decision(current: str, candidate: str) -> str:
    rank = {"pass": 0, "warning": 1, "reject": 2}
    return candidate if rank[candidate] > rank[current] else current


def validate_image(
    image: Image.Image,
    file_size_bytes: int,
    settings: ReconstructionSettings,
    manifest_sample: ManifestSample | None = None,
) -> ValidationResult:
    width, height = image.size
    aspect_ratio = round(width / float(max(height, 1)), 4)
    brightness = round(brightness_mean(image), 4)
    blur = round(blur_score(image), 4)
    portrait = portrait_bias(image)

    decision = "pass"
    reasons: list[str] = []
    warning_flags: list[str] = []

    if width < settings.min_width_reject or height < settings.min_height_reject:
        decision = _merge_decision(decision, "reject")
        reasons.append("LOW_RESOLUTION_REJECT")
    elif width < settings.min_width_warning or height < settings.min_height_warning:
        decision = _merge_decision(decision, "warning")
        warning_flags.append("LOW_RESOLUTION_WARNING")

    if aspect_ratio < settings.aspect_ratio_reject_min or aspect_ratio > settings.aspect_ratio_reject_max:
        decision = _merge_decision(decision, "reject")
        reasons.append("ASPECT_RATIO_REJECT")
    elif aspect_ratio < settings.aspect_ratio_warning_min or aspect_ratio > settings.aspect_ratio_warning_max:
        decision = _merge_decision(decision, "warning")
        warning_flags.append("ASPECT_RATIO_WARNING")

    if brightness < settings.brightness_reject:
        decision = _merge_decision(decision, "reject")
        reasons.append("LOW_LIGHT_REJECT")
    elif brightness < settings.brightness_warning:
        decision = _merge_decision(decision, "warning")
        warning_flags.append("LOW_LIGHT_WARNING")

    if blur < settings.blur_reject:
        decision = _merge_decision(decision, "reject")
        reasons.append("BLUR_REJECT")
    elif blur < settings.blur_warning:
        decision = _merge_decision(decision, "warning")
        warning_flags.append("BLUR_WARNING")

    if manifest_sample is not None:
        manifest_decision, manifest_reasons, manifest_warnings = validate_manifest_labels(manifest_sample)
        decision = _merge_decision(decision, manifest_decision)
        reasons.extend(manifest_reasons)
        warning_flags.extend(manifest_warnings)

    reasons = sorted(set(reasons))
    warning_flags = sorted(set(warning_flags))
    metrics = ValidationMetrics(
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        brightness_mean=brightness,
        blur_score=blur,
        portrait_bias=portrait,
        file_size_bytes=file_size_bytes,
    )
    return ValidationResult(
        decision=decision,  # type: ignore[arg-type]
        reasons=reasons,
        warning_flags=warning_flags,
        metrics=metrics,
        expected_label=manifest_sample.split_label if manifest_sample else None,
    )


def validate_manifest_labels(sample: ManifestSample) -> tuple[str, list[str], list[str]]:
    decision = "pass"
    reasons: list[str] = []
    warnings: list[str] = []

    if sample.subject_count != "single":
        decision = _merge_decision(decision, "reject")
        reasons.append("MULTI_PERSON")

    if sample.body_visibility == "truncated_major":
        decision = _merge_decision(decision, "reject")
        reasons.append("BODY_TRUNCATED")
    elif sample.body_visibility == "partial":
        decision = _merge_decision(decision, "warning")
        warnings.append("BODY_PARTIAL")

    if sample.occlusion_level == "high":
        decision = _merge_decision(decision, "reject")
        reasons.append("SEVERE_OCCLUSION")
    elif sample.occlusion_level == "medium":
        decision = _merge_decision(decision, "warning")
        warnings.append("MEDIUM_OCCLUSION")

    if sample.lighting_level == "very_dark":
        decision = _merge_decision(decision, "reject")
        reasons.append("LOW_LIGHT")
    elif sample.lighting_level == "dark":
        decision = _merge_decision(decision, "warning")
        warnings.append("LOW_LIGHT")

    if sample.blur_level == "high":
        decision = _merge_decision(decision, "reject")
        reasons.append("HEAVY_BLUR")
    elif sample.blur_level == "medium":
        decision = _merge_decision(decision, "warning")
        warnings.append("MEDIUM_BLUR")

    if sample.perspective_level == "extreme":
        decision = _merge_decision(decision, "reject")
        reasons.append("EXTREME_PERSPECTIVE")
    elif sample.perspective_level == "mild":
        decision = _merge_decision(decision, "warning")
        warnings.append("MILD_PERSPECTIVE")

    if sample.clothing_looseness in {"loose", "very_loose"}:
        decision = _merge_decision(decision, "warning")
        warnings.append("LOOSE_CLOTHING")

    if sample.primary_reason:
        if sample.split_label == "reject":
            decision = _merge_decision(decision, "reject")
            reasons.append(sample.primary_reason)
        elif sample.split_label == "warning":
            decision = _merge_decision(decision, "warning")
            warnings.append(sample.primary_reason)

    for secondary in sample.secondary_reason_list:
        warnings.append(secondary)

    return decision, sorted(set(reasons)), sorted(set(warnings))
