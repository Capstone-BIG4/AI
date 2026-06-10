from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps

from pipeline_common import PIPELINE, ROOT, ensure_dir, image_info, relative, resolve_input_path, write_json


INPUTS = {
    "person": resolve_input_path("person"),
    "top_front": resolve_input_path("top_front"),
    "top_back": resolve_input_path("top_back"),
    "pants_front": resolve_input_path("pants_front"),
    "pants_back": resolve_input_path("pants_back"),
}


def save_png(image: Image.Image, path: Path) -> None:
    ensure_dir(path.parent)
    image.save(path)


def normalize_person() -> dict:
    out_dir = ensure_dir(PIPELINE / "preprocessed")
    src = INPUTS["person"]
    curated_crop = ROOT / "assets" / "processed" / "person-crop.jpg"
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    oriented = out_dir / "person_oriented.png"
    save_png(im, oriented)

    if curated_crop.exists():
        crop = ImageOps.exif_transpose(Image.open(curated_crop)).convert("RGB")
        crop_path = out_dir / "person_crop.png"
        save_png(crop, crop_path)
        # SAM 3D Body is more stable on the tighter person crop. Keep the full original
        # as source evidence, but use the curated crop as the inference-oriented image.
        save_png(crop, oriented)
        mask = Image.new("L", crop.size, 255)
        mask_path = out_dir / "person_mask.png"
        save_png(mask, mask_path)
        metadata = {
            "source": relative(src),
            "oriented": relative(oriented),
            "crop": relative(crop_path),
            "mask": relative(mask_path),
            "original_size": [im.width, im.height],
            "crop_box_xyxy": None,
            "method": "reuse_existing_curated_person_crop_for_sam_stability",
            "curated_crop_source": relative(curated_crop),
        }
        write_json(out_dir / "crop_metadata.json", metadata)
        return metadata

    # Conservative full-body crop: remove only obvious flat border/background.
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg).convert("L")
    mask = diff.point(lambda px: 255 if px > 18 else 0).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3))
    bbox = mask.getbbox()
    if bbox is None:
        bbox = (0, 0, im.width, im.height)
    pad_x = int((bbox[2] - bbox[0]) * 0.08)
    pad_y = int((bbox[3] - bbox[1]) * 0.06)
    crop_box = (
        max(0, bbox[0] - pad_x),
        max(0, bbox[1] - pad_y),
        min(im.width, bbox[2] + pad_x),
        min(im.height, bbox[3] + pad_y),
    )
    crop = im.crop(crop_box)
    if crop.height > 1400:
        new_w = max(1, int(crop.width * 1400 / crop.height))
        crop = crop.resize((new_w, 1400), Image.Resampling.LANCZOS)
    crop_path = out_dir / "person_crop.png"
    save_png(crop, crop_path)

    mask_crop = mask.crop(crop_box).resize(crop.size, Image.Resampling.BILINEAR)
    mask_path = out_dir / "person_mask.png"
    save_png(mask_crop.convert("L"), mask_path)

    metadata = {
        "source": relative(src),
        "oriented": relative(oriented),
        "crop": relative(crop_path),
        "mask": relative(mask_path),
        "original_size": [im.width, im.height],
        "crop_box_xyxy": list(crop_box),
        "method": "exif_transpose_plus_corner_background_difference",
    }
    write_json(out_dir / "crop_metadata.json", metadata)
    return metadata


def alpha_from_background(im: Image.Image) -> Image.Image:
    rgba = im.convert("RGBA")
    arr = np.asarray(rgba).astype(np.int16)
    if arr[:, :, 3].min() < 250:
        alpha = np.asarray(rgba)[:, :, 3]
    else:
        corners = np.array(
            [
                arr[0, 0, :3],
                arr[0, -1, :3],
                arr[-1, 0, :3],
                arr[-1, -1, :3],
            ],
            dtype=np.float32,
        )
        bg = np.median(corners, axis=0)
        dist = np.linalg.norm(arr[:, :, :3].astype(np.float32) - bg, axis=2)
        alpha = (dist > 22).astype(np.uint8) * 255
        alpha_img = Image.fromarray(alpha).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
        alpha = np.asarray(alpha_img.point(lambda px: 255 if px > 40 else 0), dtype=np.uint8)
    out = np.asarray(rgba).copy()
    out[:, :, 3] = alpha
    return Image.fromarray(out)


def light_detail_mask(cutout: Image.Image, min_alpha: int = 30) -> Image.Image:
    arr = np.asarray(cutout.convert("RGBA"))
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    white_like = (rgb[:, :, 0] > 170) & (rgb[:, :, 1] > 170) & (rgb[:, :, 2] > 170) & (alpha > min_alpha)
    return Image.fromarray((white_like.astype(np.uint8) * 255)).filter(ImageFilter.MaxFilter(3))


def pants_pocket_mask(cutout: Image.Image) -> Image.Image:
    arr = np.asarray(cutout.convert("RGBA"))
    alpha = arr[:, :, 3] > 20
    gray = np.mean(arr[:, :, :3], axis=2)
    edges = np.zeros_like(gray, dtype=np.float32)
    edges[:, 1:] += np.abs(gray[:, 1:] - gray[:, :-1])
    edges[1:, :] += np.abs(gray[1:, :] - gray[:-1, :])
    mask = (edges > 18) & alpha
    return Image.fromarray((mask.astype(np.uint8) * 255)).filter(ImageFilter.MaxFilter(3))


def prepare_garments() -> dict:
    out_dir = ensure_dir(PIPELINE / "garments")
    outputs: dict[str, str] = {}
    for key in ["top_front", "top_back", "pants_front", "pants_back"]:
        im = ImageOps.exif_transpose(Image.open(INPUTS[key]))
        cutout = alpha_from_background(im)
        path = out_dir / f"{key}_cutout.png"
        save_png(cutout, path)
        outputs[f"{key}_cutout"] = relative(path)

    masks = {
        "top_front_logo_mask": light_detail_mask(Image.open(out_dir / "top_front_cutout.png")),
        "top_back_logo_mask": light_detail_mask(Image.open(out_dir / "top_back_cutout.png")),
        "pants_back_pocket_mask": pants_pocket_mask(Image.open(out_dir / "pants_back_cutout.png")),
    }
    for name, mask in masks.items():
        path = out_dir / f"{name}.png"
        save_png(mask, path)
        outputs[name] = relative(path)

    metadata = {
        "sources": {name: relative(path) for name, path in INPUTS.items() if name != "person"},
        "outputs": outputs,
        "view_assignment": {
            "front": ["top_front_cutout", "pants_front_cutout"],
            "side": ["top_front_cutout", "top_back_cutout", "pants_front_cutout", "pants_back_cutout"],
            "back": ["top_back_cutout", "pants_back_cutout"],
        },
        "method": "alpha_preserve_or_corner_background_removal_plus_light_detail_masks",
        "image_info": {name: image_info(ROOT / path) for name, path in outputs.items()},
    }
    write_json(out_dir / "garment_metadata.json", metadata)
    return metadata


def main() -> int:
    person = normalize_person()
    garments = prepare_garments()
    print("person_crop=" + person["crop"])
    print("garment_metadata=assets/pipeline/garments/garment_metadata.json")
    print("garments_prepared=" + str(len(garments["outputs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
