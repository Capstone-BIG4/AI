from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline_common import PIPELINE, ROOT, ensure_dir, image_info, now_iso, read_json, relative, write_json


WEIGHTS_DIR = ROOT / "external" / "fashn-vton-1.5" / "weights"
BASE_MANIFEST = PIPELINE / "sam_body_only" / "base" / "sam_body_only_base_manifest.json"
OUT_DIR = PIPELINE / "sam_body_only" / "fashn"
GARMENTS = {
    "front": {
        "top": ROOT / "image" / "top_front.png",
        "pants": ROOT / "image" / "front_pants.png",
    },
    "side": {
        "top": ROOT / "image" / "top_front.png",
        "pants": ROOT / "image" / "front_pants.png",
    },
    "back": {
        "top": ROOT / "image" / "top_back.png",
        "pants": ROOT / "image" / "back_pants.png",
    },
}
FORBIDDEN_REFERENCES = {
    "guide/mannequin-front.png",
    "guide/mannequin-side.png",
    "guide/mannequin-back.png",
}


def run_stage(pipeline, person: Image.Image, garment: Image.Image, category: str, seed: int, timesteps: int, guidance: float) -> Image.Image:
    result = pipeline(
        person_image=person,
        garment_image=garment,
        category=category,
        garment_photo_type="flat-lay",
        num_samples=1,
        num_timesteps=timesteps,
        guidance_scale=guidance,
        seed=seed,
        segmentation_free=True,
    )
    return result.images[0]


def resize_back(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image
    return image.resize(size, Image.Resampling.LANCZOS)


def make_contact_sheet(items: list[tuple[str, Path]], path: Path) -> None:
    if not items:
        return
    thumb_w, thumb_h = 250, 375
    label_h = 34
    cols = min(3, len(items))
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (246, 244, 238))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (label, image_path) in enumerate(items):
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x0 = (idx % cols) * thumb_w
        y0 = (idx // cols) * (thumb_h + label_h)
        draw.text((x0 + 8, y0 + 10), label, fill=(25, 27, 25), font=font)
        sheet.paste(image, (x0 + (thumb_w - image.width) // 2, y0 + label_h + (thumb_h - image.height) // 2))
    ensure_dir(path.parent)
    sheet.save(path)


def base_path_for(view: str, base_manifest: dict) -> Path:
    item = base_manifest["outputs"][view]
    source_paths = set(item.get("source", []))
    if source_paths & FORBIDDEN_REFERENCES:
        raise AssertionError(f"Forbidden guide/mannequin reference in base source for {view}")
    return ROOT / item["path"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--views", nargs="+", default=["front", "side", "back"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[2101])
    parser.add_argument("--timesteps", type=int, default=24)
    parser.add_argument("--guidance", type=float, default=1.65)
    args = parser.parse_args()

    for required in (
        WEIGHTS_DIR / "model.safetensors",
        WEIGHTS_DIR / "dwpose" / "yolox_l.onnx",
        WEIGHTS_DIR / "dwpose" / "dw-ll_ucoco_384.onnx",
        BASE_MANIFEST,
    ):
        if not required.exists():
            raise SystemExit(f"Missing dependency: {required}")

    from fashn_vton import TryOnPipeline

    base_manifest = read_json(BASE_MANIFEST)
    ensure_dir(OUT_DIR)
    pipeline = TryOnPipeline(weights_dir=str(WEIGHTS_DIR), device="cuda")
    candidates = []
    sheet_items = []
    for view in args.views:
        base_path = base_path_for(view, base_manifest)
        source = Image.open(base_path).convert("RGB")
        original_size = source.size
        top = Image.open(GARMENTS[view]["top"]).convert("RGB")
        pants = Image.open(GARMENTS[view]["pants"]).convert("RGB")
        view_dir = ensure_dir(OUT_DIR / view)
        for seed in args.seeds:
            top_generated = run_stage(pipeline, source, top, "tops", seed, args.timesteps, args.guidance)
            top_generated = resize_back(top_generated, original_size)
            top_path = view_dir / f"seed{seed}_top.png"
            top_generated.save(top_path)

            final_generated = run_stage(pipeline, top_generated, pants, "bottoms", seed + 101, args.timesteps, args.guidance)
            final_generated = resize_back(final_generated, original_size)
            final_path = view_dir / f"seed{seed}_top_then_pants.png"
            final_generated.save(final_path)
            source_chain = [
                relative(base_path),
                "assets/pipeline/sam3d/native_output.pt",
                "assets/pipeline/sam3d/body.ply",
                "assets/pipeline/viewer_hq/sam_measurements.json",
                "assets/pipeline/sam_body_only/base/sam_body_only_base_manifest.json",
                relative(top_path),
                relative(GARMENTS[view]["top"]),
                relative(GARMENTS[view]["pants"]),
            ]
            if set(source_chain) & FORBIDDEN_REFERENCES:
                raise AssertionError(f"Forbidden guide/mannequin reference in candidate source for {view}")
            candidates.append(
                {
                    "id": f"{view}-sam-body-only-fashn-seed{seed}-top-then-pants",
                    "view": view,
                    "path": relative(final_path),
                    "upper_stage": relative(top_path),
                    "base_person": relative(base_path),
                    "source": source_chain,
                    "top_garment": relative(GARMENTS[view]["top"]),
                    "pants_garment": relative(GARMENTS[view]["pants"]),
                    "model": "fashn-vton-v1.5-local",
                    "seed": seed,
                    "timesteps": args.timesteps,
                    "guidance": args.guidance,
                    "image": image_info(final_path),
                    "claim_level": "sam-body-only-generated-candidate",
                    "notes": "Generated from the SAM Body measurement-derived mannequin base. guide/mannequin reference images are not used.",
                }
            )
            sheet_items.append((f"{view} seed{seed}", final_path))
            print(f"{view}_seed{seed}={relative(final_path)}")

    contact_sheet = OUT_DIR / "contact_sheet.png"
    make_contact_sheet(sheet_items, contact_sheet)
    manifest = {
        "generated_at": now_iso(),
        "model": "fashn-vton-v1.5-local",
        "weights_dir": relative(WEIGHTS_DIR),
        "base_manifest": relative(BASE_MANIFEST),
        "views": args.views,
        "seeds": args.seeds,
        "timesteps": args.timesteps,
        "guidance": args.guidance,
        "forbidden_inputs": sorted(FORBIDDEN_REFERENCES),
        "candidates": candidates,
        "contact_sheet": relative(contact_sheet),
        "disclosure": "Generated candidates use only the SAM Body measurement-derived mannequin base as the person target. User-created guide/mannequin reference images are excluded.",
    }
    write_json(OUT_DIR / "sam_body_only_fashn_candidates.json", manifest)
    print("status=success")
    print(f"manifest={relative(OUT_DIR / 'sam_body_only_fashn_candidates.json')}")
    print(f"contact_sheet={relative(contact_sheet)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
