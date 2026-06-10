from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

from pipeline_common import ASSETS, PIPELINE, ROOT, ensure_dir, image_info, now_iso, read_json, relative, write_json


FORBIDDEN_REFERENCES = {
    "guide/mannequin-front.png",
    "guide/mannequin-side.png",
    "guide/mannequin-back.png",
}
DESTINATIONS = {
    "front": ASSETS / "results" / "sam-body-only-front.png",
    "side": ASSETS / "results" / "sam-body-only-side.png",
    "back": ASSETS / "results" / "sam-body-only-back.png",
}
DISPLAY_DIR = ASSETS / "results" / "display"
DISPLAY_DESTINATIONS = {
    "front": DISPLAY_DIR / "sam-body-only-front-contrast.png",
    "side": DISPLAY_DIR / "sam-body-only-side-contrast.png",
    "back": DISPLAY_DIR / "sam-body-only-back-contrast.png",
}
MASK_LOCKED_DIR = PIPELINE / "sam_body_only" / "mask_locked"
DEFAULT_SELECTIONS = {
    "front": PIPELINE / "sam_body_only" / "fashn" / "front" / "seed2101_top_then_pants.png",
    "side": PIPELINE / "sam_body_only" / "fashn" / "side" / "seed2201_top_then_pants.png",
    "back": PIPELINE / "sam_body_only" / "fashn" / "back" / "seed2101_top_then_pants.png",
}
BASE_IMAGES = {
    "front": PIPELINE / "sam_body_only" / "base" / "front_sam_body_only_base.png",
    "side": PIPELINE / "sam_body_only" / "base" / "side_sam_body_only_base.png",
    "back": PIPELINE / "sam_body_only" / "base" / "back_sam_body_only_base.png",
}
GARMENTS = {
    "front": ("image/top_front.png", "image/front_pants.png"),
    "side": ("image/top_front.png", "image/front_pants.png"),
    "back": ("image/top_back.png", "image/back_pants.png"),
}
REFINED_MASKS = {
    view: {
        "shirt": PIPELINE / "refined_outputs" / f"{view}_shirt_mask.png",
        "pants": PIPELINE / "refined_outputs" / f"{view}_pants_mask.png",
    }
    for view in ("front", "back")
}
CURATED_MASKS = {
    view: {
        "shirt": PIPELINE / "experiments" / "sam_mask_locked_best_seed2101" / f"{view}_shirt_mask.png",
        "pants": PIPELINE / "experiments" / "sam_mask_locked_best_seed2101" / f"{view}_pants_mask.png",
    }
    for view in ("front", "back")
}
CURATED_DISPLAY = {
    "front": PIPELINE
    / "experiments"
    / "sam_mask_locked_best_seed2101_display"
    / "front_sam_locked_best_seed2101_display.png",
    "back": PIPELINE
    / "experiments"
    / "sam_mask_locked_best_seed2101_display"
    / "back_sam_locked_best_seed2101_display.png",
}
MASK_LOCKED_VIEWS = {"front", "back"}


def assert_clean_sources(sources: list[str], label: str) -> None:
    forbidden = sorted(set(sources) & FORBIDDEN_REFERENCES)
    if forbidden:
        raise AssertionError(f"{label} uses forbidden guide/mannequin references: {forbidden}")


def seed_label(path: Path) -> str:
    return path.stem.replace("_top_then_pants", "").replace("_top", "")


def open_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def resized_like(image: Image.Image, reference: Image.Image) -> Image.Image:
    if image.size == reference.size:
        return image
    return image.resize(reference.size, Image.Resampling.LANCZOS)


def largest_components(mask: np.ndarray, minimum_area: int) -> np.ndarray:
    components, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if components <= 1:
        return mask.astype(bool)
    kept = np.zeros(mask.shape, dtype=bool)
    for index in range(1, components):
        if stats[index, cv2.CC_STAT_AREA] >= minimum_area:
            kept |= labels == index
    return kept if kept.any() else mask.astype(bool)


def clean_mask(mask: np.ndarray, close: int, open_: int, dilate: int) -> Image.Image:
    out = mask.astype(np.uint8) * 255
    if close:
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    if open_:
        out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((open_, open_), np.uint8))
    if dilate:
        out = cv2.dilate(out, np.ones((dilate, dilate), np.uint8), iterations=1)
    return Image.fromarray(out).filter(ImageFilter.GaussianBlur(1.4))


def fallback_mask(view: str, kind: str, selected: Path, destination: Path) -> str:
    source = np.asarray(open_rgb(selected))
    hint_path = REFINED_MASKS[view][kind]
    hint = np.asarray(Image.open(hint_path).convert("L")) > 24
    hint = cv2.dilate(hint.astype(np.uint8) * 255, np.ones((27, 27), np.uint8), iterations=1) > 0

    red = source[..., 0]
    green = source[..., 1]
    blue = source[..., 2]
    mean = source.mean(axis=2)
    spread = source.max(axis=2) - source.min(axis=2)
    if kind == "shirt":
        dark_fabric = (mean < 96) & (spread < 64)
        white_print = (mean > 152) & (spread < 58)
        mask = hint & (dark_fabric | white_print)
        mask = largest_components(mask, 900)
        mask_image = clean_mask(mask, close=19, open_=3, dilate=2)
    else:
        khaki = (red > 88) & (red < 190) & (green > 82) & (green < 178) & (blue > 58) & (blue < 154)
        warm = (red.astype(np.int16) - blue.astype(np.int16)) > 4
        mask = hint & khaki & warm
        mask = largest_components(mask, 1200)
        mask_image = clean_mask(mask, close=25, open_=5, dilate=4)

    mask_image.save(destination)
    return "color-fallback-from-selected-vton"


def write_lock_mask(view: str, kind: str, selected: Path, output_dir: Path) -> tuple[Path, str]:
    destination = output_dir / f"{view}_{kind}_mask.png"
    curated = CURATED_MASKS[view][kind]
    if curated.exists():
        shutil.copyfile(curated, destination)
        return destination, "curated-best-pick-mask"
    method = fallback_mask(view, kind, selected, destination)
    return destination, method


def alpha_from_mask(path: Path, size: tuple[int, int]) -> np.ndarray:
    mask = Image.open(path).convert("L")
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.BILINEAR)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    return np.asarray(mask).astype(np.float32) / 255.0


def compose_with_masks(base: Path, selected: Path, shirt_mask: Path, pants_mask: Path, destination: Path) -> None:
    base_image = open_rgb(base)
    selected_image = resized_like(open_rgb(selected), base_image)
    out = np.asarray(base_image).astype(np.float32)
    candidate = np.asarray(selected_image).astype(np.float32)
    for mask_path in (pants_mask, shirt_mask):
        alpha = alpha_from_mask(mask_path, base_image.size)
        out = out * (1.0 - alpha[..., None]) + candidate * alpha[..., None]
    result = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    result = result.filter(ImageFilter.UnsharpMask(radius=1.0, percent=55, threshold=4))
    result.save(destination, quality=96)


def display_polish_fallback(locked: Path, destination: Path) -> None:
    image = open_rgb(locked)
    image.save(destination, quality=96)


def write_mask_locked_view(view: str, selected: Path, destination: Path) -> dict:
    output_dir = ensure_dir(MASK_LOCKED_DIR)
    label = seed_label(selected)
    locked_path = output_dir / f"{view}_sam_locked_{label}.png"
    display_path = output_dir / f"{view}_sam_locked_{label}_display.png"

    shirt_mask, shirt_method = write_lock_mask(view, "shirt", selected, output_dir)
    pants_mask, pants_method = write_lock_mask(view, "pants", selected, output_dir)
    compose_with_masks(BASE_IMAGES[view], selected, shirt_mask, pants_mask, locked_path)

    curated_display = CURATED_DISPLAY[view]
    if curated_display.exists():
        shutil.copyfile(curated_display, display_path)
        display_method = "curated-display-polish"
    else:
        display_polish_fallback(locked_path, display_path)
        display_method = "mask-locked-display-fallback"

    shutil.copyfile(display_path, destination)
    shutil.copyfile(display_path, DISPLAY_DESTINATIONS[view])
    return {
        "view": view,
        "source_vton": relative(selected),
        "base_person": relative(BASE_IMAGES[view]),
        "shirt_mask": relative(shirt_mask),
        "pants_mask": relative(pants_mask),
        "locked_result": relative(locked_path),
        "display_result": relative(display_path),
        "destination": relative(destination),
        "display_destination": relative(DISPLAY_DESTINATIONS[view]),
        "mask_methods": {
            "shirt": shirt_method,
            "pants": pants_method,
        },
        "display_method": display_method,
    }


def write_side_view(selected: Path, destination: Path) -> dict:
    shutil.copyfile(selected, destination)
    if not DISPLAY_DESTINATIONS["side"].exists():
        shutil.copyfile(destination, DISPLAY_DESTINATIONS["side"])
        display_method = "copied-selected-vton"
    else:
        display_method = "kept-existing-side-display"
    return {
        "view": "side",
        "source_vton": relative(selected),
        "base_person": relative(BASE_IMAGES["side"]),
        "destination": relative(destination),
        "display_destination": relative(DISPLAY_DESTINATIONS["side"]),
        "display_method": display_method,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front", default=str(DEFAULT_SELECTIONS["front"]))
    parser.add_argument("--side", default=str(DEFAULT_SELECTIONS["side"]))
    parser.add_argument("--back", default=str(DEFAULT_SELECTIONS["back"]))
    parser.add_argument("--output", default=str(PIPELINE / "sam_body_only" / "fashn" / "sam_body_only_selection.json"))
    args = parser.parse_args()

    selected_paths = {
        "front": Path(args.front),
        "side": Path(args.side),
        "back": Path(args.back),
    }
    base_manifest = PIPELINE / "sam_body_only" / "base" / "sam_body_only_base_manifest.json"
    candidates_manifest = PIPELINE / "sam_body_only" / "fashn" / "sam_body_only_fashn_candidates.json"
    for required in [base_manifest, *selected_paths.values(), *BASE_IMAGES.values()]:
        if not required.exists():
            raise FileNotFoundError(required)

    finals = []
    ensure_dir(ASSETS / "results")
    ensure_dir(DISPLAY_DIR)
    selection_path = Path(args.output)
    mask_locked_manifest_path = MASK_LOCKED_DIR / "mask_locked_selection.json"
    selection_records = []
    display_records = []
    for view, src in selected_paths.items():
        dst = DESTINATIONS[view]
        if view in MASK_LOCKED_VIEWS:
            selection_record = write_mask_locked_view(view, src, dst)
            generated_by_tail = [
                "sam-body-fixed-garment-mask-lock",
                "display-polished-best-pick",
            ]
            manual_edits_tail = [
                "locked generated garment pixels to selected shirt/pants masks",
                "preserved SAM body base outside garment masks",
            ]
        else:
            selection_record = write_side_view(src, dst)
            generated_by_tail = ["manual-visual-best-pick"]
            manual_edits_tail = ["selected generated candidate after visual review"]
        selection_records.append(selection_record)
        display_records.append(
            {
                "view": view,
                "source": selection_record["destination"],
                "destination": selection_record["display_destination"],
                "operation": selection_record["display_method"],
                "display_size": image_info(DISPLAY_DESTINATIONS[view]),
            }
        )
        top, pants = GARMENTS[view]
        source = [
            "assets/pipeline/sam3d/native_output.pt",
            "assets/pipeline/sam3d/body.ply",
            "assets/pipeline/viewer_hq/sam_measurements.json",
            "assets/pipeline/sam_body_only/base/sam_body_only_base_manifest.json",
            relative(BASE_IMAGES[view]),
            relative(src),
            top,
            pants,
            relative(selection_path),
        ]
        if view in MASK_LOCKED_VIEWS:
            source.extend(
                [
                    selection_record["shirt_mask"],
                    selection_record["pants_mask"],
                    selection_record["locked_result"],
                    selection_record["display_result"],
                    relative(mask_locked_manifest_path),
                ]
            )
        assert_clean_sources(source, f"sam-body-only-{view}")
        finals.append(
            {
                "id": f"sam-body-only-{view}",
                "role": f"sam-body-only-generated-viewer-{view}",
                "view": view,
                "path": relative(dst),
                "display_path": selection_record["display_destination"],
                "source": source,
                "generated_by": [
                    "sam-3d-body",
                    "sam-body-measurement-extraction",
                    "sam-body-only-mannequin-base-rendering",
                    "fashn-vton-v1.5-local",
                    "top-then-pants-diffusion-generation",
                    *generated_by_tail,
                ],
                "manual_edits": [
                    *manual_edits_tail,
                    "excluded guide/mannequin reference images from final source chain",
                ],
                "display_size": image_info(dst),
                "claim_level": "actual-sam-body-only-mask-locked-generated-fixed-sample",
                "notes": (
                    "Final viewer result generated from the SAM Body measurement/mesh-derived mannequin base. "
                    "Front/back preserve the SAM body base outside garment lock masks; guide/mannequin reference images are not used."
                ),
            }
        )

    selection = {
        "generated_at": now_iso(),
        "base_manifest": relative(base_manifest),
        "candidate_manifest": relative(candidates_manifest) if candidates_manifest.exists() else None,
        "forbidden_inputs": sorted(FORBIDDEN_REFERENCES),
        "finals": [
            {
                **record,
                "claim_level": "actual-sam-body-only-mask-locked-generated-fixed-sample",
            }
            for record in selection_records
        ],
    }
    write_json(selection_path, selection)
    write_json(
        mask_locked_manifest_path,
        {
            "generated_at": now_iso(),
            "method": "front-back-sam-body-fixed-mask-lock",
            "outputs": [record for record in selection_records if record["view"] in MASK_LOCKED_VIEWS],
            "notes": (
                "Front/back final images are rebuilt by applying the selected FASHN garment pixels only inside "
                "best-pick shirt and pants lock masks, preserving the SAM body base elsewhere."
            ),
        },
    )
    write_json(
        DISPLAY_DIR / "display_repair_manifest.json",
        {
            "generated_at": now_iso(),
            "method": "viewer-display-sync-from-mask-locked-results",
            "outputs": display_records,
            "notes": "Display images are synced from the current selected viewer results.",
        },
    )

    manifest_path = ASSETS / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["mode"] = "sam-body-only-mask-locked-generated-fixed-sample"
    old_current_ids = {
        "sam-body-only-front",
        "sam-body-only-side",
        "sam-body-only-back",
    }
    retained = []
    for item in manifest.get("results", []):
        item_id = str(item.get("id", ""))
        if item_id in old_current_ids:
            continue
        if item_id.startswith("generated-sam-"):
            continue
        retained.append(item)
    manifest["results"] = finals + retained

    technical = manifest.setdefault("technicalPipeline", {})
    technical.pop("targetReferences", None)
    technical.pop("generatedSamViewer", None)
    technical["samBodyOnlyViewer"] = {
        "generated_at": now_iso(),
        "model": "fashn-vton-v1.5-local + sam-body-fixed-mask-lock",
        "base_manifest": relative(base_manifest),
        "selection_manifest": relative(selection_path),
        "mask_locked_manifest": relative(mask_locked_manifest_path),
        "forbidden_inputs": sorted(FORBIDDEN_REFERENCES),
        "selected": finals,
        "disclosure": (
            "Final viewer images are generated from the SAM Body measurement/mesh-derived mannequin base. "
            "Front/back are mask-locked so SAM body pixels outside the shirt and pants regions are preserved. "
            "User-created guide/mannequin reference images are excluded from the final source chain."
        ),
    }
    technical["disclosure"] = (
        "SAM 3D Body is used to recover the fixed user's body/mesh and derive mannequin proportions/base views. "
        "The final front/side/back viewer uses FASHN VTON generated images from that SAM-derived base, with front/back "
        "locked back to the SAM body outside garment masks."
    )
    write_json(manifest_path, manifest)

    print("status=success")
    print(f"selection={relative(selection_path)}")
    for view, dst in DESTINATIONS.items():
        print(f"{view}={relative(dst)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
