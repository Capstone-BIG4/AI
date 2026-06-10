from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from pipeline_common import PIPELINE, ensure_dir, now_iso, read_json, relative, write_json


SIZE = (1024, 1536)


def body_layout(view: str, measurements: dict) -> dict[str, tuple[int, int, int, int]]:
    w, h = SIZE
    shoulder_ratio = measurements.get("normalized", {}).get("shoulder_width", 0.23)
    hip_ratio = measurements.get("normalized", {}).get("hip_to_shoulder", 0.78)
    shoulder = int(max(250, min(360, h * shoulder_ratio * 0.95)))
    if view == "side":
        shoulder = int(shoulder * 0.46)
    hip = int(shoulder * max(0.62, min(0.98, hip_ratio)))
    cx = w // 2
    top = 118
    head_w = 146 if view != "side" else 132
    head_h = 190
    neck_w = 72 if view != "side" else 52
    torso_top = top + head_h + 44
    waist_y = 748
    crotch_y = 835
    ankle_y = 1406
    return {
        "head": (cx - head_w // 2, top, cx + head_w // 2, top + head_h),
        "neck": (cx - neck_w // 2, top + head_h - 8, cx + neck_w // 2, torso_top + 18),
        "torso": (cx - shoulder // 2, torso_top, cx + shoulder // 2, waist_y),
        "hip": (cx - hip // 2, waist_y - 20, cx + hip // 2, crotch_y + 24),
        "left_arm": (cx - shoulder // 2 - 62, torso_top + 40, cx - shoulder // 2 + 38, 1058),
        "right_arm": (cx + shoulder // 2 - 38, torso_top + 40, cx + shoulder // 2 + 62, 1058),
        "left_leg": (cx - hip // 2 + 4, crotch_y, cx - 20, ankle_y),
        "right_leg": (cx + 20, crotch_y, cx + hip // 2 - 4, ankle_y),
        "left_shoe": (cx - hip // 2 - 8, ankle_y - 4, cx - 18, ankle_y + 42),
        "right_shoe": (cx + 18, ankle_y - 4, cx + hip // 2 + 8, ankle_y + 42),
    }


def draw_silhouette(view: str, measurements: dict) -> Image.Image:
    image = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(image)
    p = body_layout(view, measurements)
    draw.ellipse(p["head"], fill=255)
    draw.rounded_rectangle(p["neck"], radius=20, fill=255)
    draw.rounded_rectangle(p["torso"], radius=40, fill=255)
    draw.rounded_rectangle(p["hip"], radius=34, fill=255)
    for key in ("left_arm", "right_arm", "left_leg", "right_leg"):
        draw.rounded_rectangle(p[key], radius=42 if "arm" in key else 38, fill=255)
    draw.ellipse(p["left_shoe"], fill=255)
    draw.ellipse(p["right_shoe"], fill=255)
    if view == "side":
        # Keep side view narrow and single-leg dominant.
        mask = Image.new("L", SIZE, 0)
        mdraw = ImageDraw.Draw(mask)
        cx = SIZE[0] // 2
        mdraw.rounded_rectangle((cx - 118, p["torso"][1] - 10, cx + 118, p["right_shoe"][3]), radius=82, fill=255)
        image = Image.composite(image, Image.new("L", SIZE, 0), mask)
    return image.filter(ImageFilter.GaussianBlur(1.1))


def draw_depth(silhouette: Image.Image, view: str) -> Image.Image:
    w, h = SIZE
    depth = Image.new("L", SIZE, 0)
    pixels = depth.load()
    mask = silhouette.load()
    for y in range(h):
        for x in range(w):
            if mask[x, y] > 0:
                center_weight = 1 - min(abs(x - w / 2) / (w * (0.30 if view != "side" else 0.17)), 1)
                vertical = 1 - min(max((y - 120) / 1350, 0), 1) * 0.24
                pixels[x, y] = int(118 + 102 * center_weight * vertical)
    return depth.filter(ImageFilter.GaussianBlur(1.4))


def draw_normal(silhouette: Image.Image, view: str) -> Image.Image:
    w, h = SIZE
    normal = Image.new("RGB", SIZE, (0, 0, 0))
    pixels = normal.load()
    mask = silhouette.load()
    for y in range(h):
        for x in range(w):
            if mask[x, y] > 0:
                xr = (x - w / 2) / (w / 2)
                red = int(128 + max(min(xr * 66, 66), -66))
                green = int(126 + (0.5 - y / h) * 42)
                blue = 224 if view != "back" else 202
                pixels[x, y] = (red, green, blue)
    return normal.filter(ImageFilter.GaussianBlur(1.0))


def draw_region_mask(kind: str, layout: dict) -> Image.Image:
    mask = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(mask)
    if kind == "top":
        draw.rounded_rectangle(layout["torso"], radius=36, fill=255)
        draw.rounded_rectangle((layout["left_arm"][0], layout["left_arm"][1], layout["left_arm"][2], layout["left_arm"][1] + 140), radius=32, fill=255)
        draw.rounded_rectangle((layout["right_arm"][0], layout["right_arm"][1], layout["right_arm"][2], layout["right_arm"][1] + 140), radius=32, fill=255)
    elif kind == "pants":
        draw.rounded_rectangle(layout["hip"], radius=26, fill=255)
        draw.rounded_rectangle(layout["left_leg"], radius=34, fill=255)
        draw.rounded_rectangle(layout["right_leg"], radius=34, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(1.2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", default=str(PIPELINE / "viewer_hq" / "sam_measurements.json"))
    parser.add_argument("--output-dir", default=str(PIPELINE / "viewer_hq" / "guides"))
    args = parser.parse_args()

    measurements = read_json(Path(args.measurements))
    out_dir = ensure_dir(Path(args.output_dir))
    outputs = {}
    for view in ("front", "side", "back"):
        layout = body_layout(view, measurements)
        silhouette = draw_silhouette(view, measurements)
        depth = draw_depth(silhouette, view)
        normal = draw_normal(silhouette, view)
        line = silhouette.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        top_mask = draw_region_mask("top", layout)
        pants_mask = draw_region_mask("pants", layout)
        view_outputs = {}
        for name, image in {
            "silhouette": silhouette,
            "depth": depth,
            "normal": normal,
            "line": line,
            "top_mask": top_mask,
            "pants_mask": pants_mask,
        }.items():
            path = out_dir / f"{view}_{name}.png"
            image.save(path)
            view_outputs[name] = relative(path)
        outputs[view] = view_outputs

    manifest = {
        "generated_at": now_iso(),
        "source_measurements": relative(Path(args.measurements)),
        "resolution": list(SIZE),
        "outputs": outputs,
        "note": "Neutral arms-down guides sized from SAM body measurements. These are control/proof assets, not final viewer images.",
    }
    write_json(out_dir / "neutral_guide_manifest.json", manifest)
    print("status=success")
    print(f"neutral_guides={relative(out_dir / 'neutral_guide_manifest.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
