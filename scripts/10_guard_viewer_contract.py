from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

from pipeline_common import ROOT


VIEWER_CONFIG = ROOT / "frontend" / "src" / "config" / "assets.js"
MANIFEST = ROOT / "assets" / "manifest.json"
FINAL_PATHS = {
    "front": "assets/results/sam-body-only-front.png",
    "side": "assets/results/sam-body-only-side.png",
    "back": "assets/results/sam-body-only-back.png",
}
DISPLAY_PATHS = {
    "front": "assets/results/display/sam-body-only-front-contrast.png",
    "side": "assets/results/display/sam-body-only-side-contrast.png",
    "back": "assets/results/display/sam-body-only-back-contrast.png",
}
FORBIDDEN_REFERENCE_PATHS = {
    "guide/mannequin-front.png",
    "guide/mannequin-side.png",
    "guide/mannequin-back.png",
}
DRAFT_PATTERN = re.compile(r"assets/results/sam-mannequin-(front|side|back)\.png")


def assert_image(path: str) -> None:
    full = ROOT / path
    if not full.exists():
        raise AssertionError(f"Missing final viewer image: {path}")
    with Image.open(full) as image:
        if image.width < 1024 or image.height < 1536:
            raise AssertionError(f"Final viewer image is too small: {path} {image.width}x{image.height}")


def main() -> int:
    app_source = VIEWER_CONFIG.read_text(encoding="utf-8")
    viewer_block = app_source.split("export const proofAssets", 1)[0]
    if DRAFT_PATTERN.search(viewer_block):
        raise AssertionError("app.js viewer assets must not point to quality-rejected sam-mannequin drafts")
    for path in DISPLAY_PATHS.values():
        if path not in viewer_block:
            raise AssertionError(f"viewer assets do not reference display result {path}")
        assert_image(path)
    for path in FINAL_PATHS.values():
        assert_image(path)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    viewer = manifest.get("result_contract", {}).get("viewer", {})
    for view, display_path in DISPLAY_PATHS.items():
        item = viewer.get(view)
        if not item:
            raise AssertionError(f"Missing viewer manifest item: {view}")
        if item.get("path") != display_path:
            raise AssertionError(f"{view} display path is {item.get('path')}, expected {display_path}")

    manifest_text = MANIFEST.read_text(encoding="utf-8")
    forbidden = sorted(path for path in FORBIDDEN_REFERENCE_PATHS if path in manifest_text)
    if forbidden:
        raise AssertionError(f"manifest must not cite guide/mannequin references: {forbidden}")

    print("status=success")
    print("viewer_contract=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
