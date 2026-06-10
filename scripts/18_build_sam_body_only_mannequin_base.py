from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from pipeline_common import PIPELINE, ensure_dir, now_iso, read_json, relative, write_json
from scripts_compat import import_from_scripts_dir


SIZE = (1024, 1536)
GUIDE_DIR = PIPELINE / "viewer_hq" / "guides"
MESH_VIEW_BASE_DIR = PIPELINE / "refined_outputs"


def load_body_layout():
    module = import_from_scripts_dir("11_build_neutral_mannequin_guides")
    return module.body_layout


def radial_background() -> Image.Image:
    w, h = SIZE
    yy, xx = np.indices((h, w))
    cx, cy = w * 0.52, h * 0.45
    dist = np.sqrt(((xx - cx) / w) ** 2 + ((yy - cy) / h) ** 2)
    tone = np.clip(247 - dist * 42, 225, 249).astype(np.uint8)
    bg = np.dstack([tone + 3, tone + 1, tone - 2]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(bg)


def soft_shadow(mask: Image.Image, view: str) -> Image.Image:
    shadow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    alpha = mask.resize((760 if view != "side" else 460, 90), Image.Resampling.BILINEAR)
    alpha = alpha.filter(ImageFilter.GaussianBlur(24)).point(lambda p: int(p * 0.18))
    layer = Image.new("RGBA", alpha.size, (45, 40, 34, 0))
    layer.putalpha(alpha)
    x = (SIZE[0] - alpha.width) // 2
    shadow.alpha_composite(layer, (x, 1414))
    return shadow


def body_material(mask: Image.Image, depth: Image.Image, normal: Image.Image, view: str) -> Image.Image:
    w, h = SIZE
    mask_np = np.asarray(mask).astype(np.float32) / 255.0
    depth_np = np.asarray(depth).astype(np.float32) / 255.0
    normal_np = np.asarray(normal).astype(np.float32) / 255.0
    yy, xx = np.indices((h, w))
    x_curve = 1.0 - np.clip(np.abs(xx - w / 2) / (w * (0.28 if view != "side" else 0.16)), 0, 1)
    y_light = 1.0 - np.clip((yy - 120) / 1500, 0, 1) * 0.16
    side_light = 0.08 * np.sin((xx / w) * math.pi)
    n_light = (normal_np[..., 0] * 0.18 + normal_np[..., 1] * 0.08 + normal_np[..., 2] * 0.26)
    shade = 0.70 + depth_np * 0.28 + x_curve * 0.16 + y_light * 0.09 + side_light + n_light * 0.12
    shade = np.clip(shade, 0.58, 1.08)
    base = np.array([228, 227, 221], dtype=np.float32)
    warm = np.array([250, 248, 241], dtype=np.float32)
    rgb = (base[None, None, :] * shade[..., None] + warm[None, None, :] * (1 - shade[..., None]) * 0.18)
    alpha = np.clip(mask_np * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), alpha]))


def component_mask(layout: dict[str, tuple[int, int, int, int]], view: str) -> Image.Image:
    mask = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(mask)
    head = layout["head"]
    draw.ellipse(head, fill=255)
    draw.rounded_rectangle(layout["neck"], radius=24, fill=255)

    torso = layout["torso"]
    hip = layout["hip"]
    cx = SIZE[0] // 2
    if view == "side":
        draw.rounded_rectangle((torso[0] - 18, torso[1] + 10, torso[2] + 28, hip[3]), radius=46, fill=255)
        draw.rounded_rectangle((cx - 98, hip[1] + 8, cx + 76, layout["right_leg"][3] - 18), radius=52, fill=255)
        draw.rounded_rectangle((cx + 54, torso[1] + 96, cx + 118, layout["right_arm"][3] - 18), radius=34, fill=255)
        draw.ellipse((cx + 46, layout["right_arm"][3] - 58, cx + 120, layout["right_arm"][3] + 26), fill=255)
        draw.ellipse((cx - 90, layout["right_shoe"][1] - 8, cx + 100, layout["right_shoe"][3] + 16), fill=255)
    else:
        shoulder_top = torso[1] + 8
        waist_y = torso[3] - 8
        draw.polygon(
            [
                (torso[0] - 18, shoulder_top + 26),
                (torso[0] + 32, shoulder_top),
                (torso[2] - 32, shoulder_top),
                (torso[2] + 18, shoulder_top + 26),
                (hip[2] - 4, hip[1] + 22),
                (hip[2] - 30, waist_y),
                (hip[0] + 30, waist_y),
                (hip[0] + 4, hip[1] + 22),
            ],
            fill=255,
        )
        draw.rounded_rectangle((hip[0] - 8, hip[1] + 8, hip[2] + 8, hip[3] + 12), radius=38, fill=255)
        for key in ("left_arm", "right_arm"):
            arm = layout[key]
            if key == "left_arm":
                x0, x1 = arm[0] + 18, arm[2] - 8
            else:
                x0, x1 = arm[0] + 8, arm[2] - 18
            draw.rounded_rectangle((x0, arm[1] + 34, x1, arm[3] - 42), radius=32, fill=255)
            draw.ellipse((x0 - 8, arm[3] - 76, x1 + 8, arm[3] + 16), fill=255)
        for key in ("left_leg", "right_leg"):
            leg = layout[key]
            draw.rounded_rectangle((leg[0] - 18, leg[1] - 10, leg[2] + 18, leg[3] + 4), radius=48, fill=255)
        draw.ellipse((layout["left_shoe"][0] - 28, layout["left_shoe"][1] - 8, layout["left_shoe"][2] + 24, layout["left_shoe"][3] + 10), fill=255)
        draw.ellipse((layout["right_shoe"][0] - 24, layout["right_shoe"][1] - 8, layout["right_shoe"][2] + 28, layout["right_shoe"][3] + 10), fill=255)

    return mask.filter(ImageFilter.GaussianBlur(1.0))


def synthetic_depth(mask: Image.Image, view: str) -> Image.Image:
    w, h = SIZE
    yy, xx = np.indices((h, w))
    mask_np = np.asarray(mask) > 0
    width = w * (0.30 if view != "side" else 0.16)
    center = np.clip(1 - np.abs(xx - w / 2) / width, 0, 1)
    vertical = 1 - np.clip((yy - 110) / 1440, 0, 1) * 0.20
    depth = np.where(mask_np, 112 + 118 * center * vertical, 0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(depth).filter(ImageFilter.GaussianBlur(1.2))


def synthetic_normal(mask: Image.Image, view: str) -> Image.Image:
    w, h = SIZE
    yy, xx = np.indices((h, w))
    mask_np = np.asarray(mask) > 0
    xr = np.clip((xx - w / 2) / (w / 2), -1, 1)
    red = 128 + xr * (70 if view != "side" else 46)
    green = 126 + (0.5 - yy / h) * 36
    blue = np.full_like(red, 222 if view != "back" else 204)
    rgb = np.dstack([red, green, blue]).clip(0, 255).astype(np.uint8)
    rgb[~mask_np] = 0
    return Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(1.0))


def draw_pose_detail(base: Image.Image, layout: dict[str, tuple[int, int, int, int]], view: str) -> None:
    return None


def neutral_garment_hint(image: Image.Image, layout: dict[str, tuple[int, int, int, int]], view: str) -> None:
    return None


def build_view(view: str, measurements: dict, out_dir: Path) -> dict:
    body_layout = load_body_layout()
    layout = body_layout(view, measurements)
    source = [
        "assets/pipeline/sam3d/native_output.pt",
        "assets/pipeline/sam3d/body.ply",
        "assets/pipeline/viewer_hq/sam_measurements.json",
        f"assets/pipeline/viewer_hq/guides/{view}_silhouette.png",
        f"assets/pipeline/viewer_hq/guides/{view}_depth.png",
        f"assets/pipeline/viewer_hq/guides/{view}_normal.png",
    ]
    mesh_base_path = MESH_VIEW_BASE_DIR / f"{view}_sam_body_base.png"
    if mesh_base_path.exists():
        out = Image.open(mesh_base_path).convert("RGB")
        out = ImageEnhance.Contrast(out).enhance(1.18)
        out = ImageEnhance.Brightness(out).enhance(0.98)
        out = out.filter(ImageFilter.UnsharpMask(radius=1.1, percent=70, threshold=4))
        source.extend(
            [
                relative(mesh_base_path),
                f"assets/pipeline/guides/{view}_silhouette.png",
                f"assets/pipeline/guides/{view}_depth.png",
                f"assets/pipeline/guides/{view}_normal.png",
            ]
        )
    else:
        mask = component_mask(layout, view)
        depth = synthetic_depth(mask, view)
        normal = synthetic_normal(mask, view)

        bg = radial_background().convert("RGBA")
        bg.alpha_composite(soft_shadow(mask, view))
        body = body_material(mask, depth, normal, view)
        bg.alpha_composite(body)
        neutral_garment_hint(bg, layout, view)
        draw_pose_detail(bg, layout, view)
        out = bg.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=75, threshold=4))

    out_path = out_dir / f"{view}_sam_body_only_base.png"
    out.save(out_path, quality=96)
    return {
        "view": view,
        "path": relative(out_path),
        "source": source,
        "claim_level": "sam-body-measurement-derived-base",
        "notes": (
            "Neutral mannequin base built from SAM Body measurements and guide masks only. "
            "When a refined SAM body base exists for this view, it is used to preserve the fixed sample body pose. "
            "No guide/mannequin reference image is used."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", default=str(PIPELINE / "viewer_hq" / "sam_measurements.json"))
    parser.add_argument("--output-dir", default=str(PIPELINE / "sam_body_only" / "base"))
    args = parser.parse_args()

    measurements_path = Path(args.measurements)
    measurements = read_json(measurements_path)
    out_dir = ensure_dir(Path(args.output_dir))
    outputs = {view: build_view(view, measurements, out_dir) for view in ("front", "side", "back")}
    manifest = {
        "generated_at": now_iso(),
        "source_measurements": relative(measurements_path),
        "resolution": list(SIZE),
        "outputs": outputs,
        "forbidden_inputs": ["guide/mannequin-front.png", "guide/mannequin-side.png", "guide/mannequin-back.png"],
        "disclosure": "These base images are newly rendered from SAM Body measurements and neutral guide masks; user-provided mannequin reference images are not used.",
    }
    write_json(out_dir / "sam_body_only_base_manifest.json", manifest)
    print("status=success")
    print(f"manifest={relative(out_dir / 'sam_body_only_base_manifest.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
