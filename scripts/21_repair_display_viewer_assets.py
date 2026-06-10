from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pipeline_common import ASSETS, ensure_dir, image_info, now_iso, relative, write_json


DISPLAY_DIR = ASSETS / "results" / "display"
SOURCE_RESULTS = {
    "front": ASSETS / "results" / "sam-body-only-front.png",
    "side": ASSETS / "results" / "sam-body-only-side.png",
    "back": ASSETS / "results" / "sam-body-only-back.png",
}
DISPLAY_RESULTS = {
    "front": DISPLAY_DIR / "sam-body-only-front-contrast.png",
    "side": DISPLAY_DIR / "sam-body-only-side-contrast.png",
    "back": DISPLAY_DIR / "sam-body-only-back-contrast.png",
}
HEAD_REPAIR = {
    "front": {
        "erase": (350, 90, 690, 430),
        "head": (438, 132, 594, 340),
        "neck": [(476, 326), (558, 326), (560, 394), (544, 414), (490, 414), (474, 394)],
    },
    "back": {
        "erase": (350, 90, 690, 420),
        "head": (438, 132, 592, 338),
        "neck": [(476, 326), (556, 326), (558, 384), (542, 404), (492, 404), (474, 384)],
    },
}


def repair_head_and_neck(display_path, source_path, destination, view):
    base = Image.open(display_path).convert("RGB")
    source = Image.open(source_path).convert("RGB")
    if base.size != source.size:
        raise ValueError(f"{view} display/source size mismatch: {base.size} != {source.size}")

    spec = HEAD_REPAIR[view]
    base_array = np.array(base)
    mask = np.zeros(base_array.shape[:2], np.uint8)
    x1, y1, x2, y2 = spec["erase"]
    region = base_array[y1:y2, x1:x2]

    pale_residue = (region[:, :, 0] > 210) & (region[:, :, 1] > 210) & (region[:, :, 2] > 198)
    mask[y1:y2, x1:x2] = pale_residue.astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=1)
    mask[base_array.mean(axis=2) < 92] = 0

    clean_background = cv2.inpaint(cv2.cvtColor(base_array, cv2.COLOR_RGB2BGR), mask, 5, cv2.INPAINT_TELEA)
    clean = Image.fromarray(cv2.cvtColor(clean_background, cv2.COLOR_BGR2RGB))

    subject_mask = Image.new("L", clean.size, 0)
    draw = ImageDraw.Draw(subject_mask)
    draw.ellipse(spec["head"], fill=255)
    draw.polygon(spec["neck"], fill=255)
    subject_mask = subject_mask.filter(ImageFilter.GaussianBlur(1.5))

    repaired = Image.composite(source, clean, subject_mask)
    repaired.save(destination)


def main() -> int:
    ensure_dir(DISPLAY_DIR)
    manifest = {
        "generated_at": now_iso(),
        "method": "display-only-neck-and-background-repair",
        "outputs": [],
        "notes": (
            "The source viewer results stay unchanged. Display copies repair only the front/back "
            "neck-head matte artifacts caused by the contrast background pass."
        ),
    }

    for view, source_path in SOURCE_RESULTS.items():
        destination = DISPLAY_RESULTS[view]
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        if view in HEAD_REPAIR:
            if not destination.exists():
                raise FileNotFoundError(destination)
            repair_head_and_neck(destination, source_path, destination, view)
            operation = "repaired-head-neck"
        else:
            if not destination.exists():
                Image.open(source_path).convert("RGB").save(destination)
            operation = "kept-existing-display"
        manifest["outputs"].append(
            {
                "view": view,
                "source": relative(source_path),
                "destination": relative(destination),
                "operation": operation,
                "display_size": image_info(destination),
            }
        )

    manifest_path = DISPLAY_DIR / "display_repair_manifest.json"
    write_json(manifest_path, manifest)
    print("status=success")
    print(f"manifest={relative(manifest_path)}")
    for item in manifest["outputs"]:
        print(f"{item['view']}={item['destination']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
