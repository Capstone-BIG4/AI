#!/usr/bin/env python3
"""Verify the Milestone 1 Three.js viewer with Playwright."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop = verify_viewport(
                browser,
                args.url,
                width=1440,
                height=960,
                screenshot_path=output_dir / "desktop-front.png",
                canvas_path=output_dir / "desktop-canvas.png",
            )
            mobile = verify_viewport(
                browser,
                args.url,
                width=390,
                height=844,
                screenshot_path=output_dir / "mobile-front.png",
                canvas_path=output_dir / "mobile-canvas.png",
            )
        finally:
            browser.close()

    print("desktop", desktop)
    print("mobile", mobile)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:4173/frontend/",
        help="Viewer URL to verify.",
    )
    parser.add_argument(
        "--output-dir",
        default="assets/sample-results/viewer",
        help="Directory for verification screenshots.",
    )
    return parser.parse_args()


def verify_viewport(
    browser,
    url: str,
    *,
    width: int,
    height: int,
    screenshot_path: Path,
    canvas_path: Path,
):
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(url, wait_until="networkidle")
    page.wait_for_function(
        "() => window.__fitPreviewReady === true",
        timeout=30000,
    )
    stats = {}
    for view in ("front", "left", "back"):
        page.locator(f"[data-view='{view}']").click()
        page.wait_for_timeout(500)
        current_canvas_path = (
            canvas_path
            if view == "front"
            else canvas_path.with_name(f"{canvas_path.stem}-{view}{canvas_path.suffix}")
        )
        page.locator("#viewer").screenshot(path=current_canvas_path)
        if view == "front":
            page.screenshot(path=screenshot_path, full_page=True)
        view_stats = analyze_canvas(current_canvas_path)
        if view_stats["non_background_pixels"] < 500:
            raise AssertionError(f"{view} canvas appears blank: {view_stats}")
        if view_stats["unique_sampled_colors"] < 16:
            raise AssertionError(f"{view} canvas has too little color variation: {view_stats}")
        stats[view] = view_stats
    page.close()
    return stats


def analyze_canvas(path: Path) -> dict[str, int]:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    pixels = image.load()
    corner_samples = [
        pixels[0, 0],
        pixels[width - 1, 0],
        pixels[0, height - 1],
        pixels[width - 1, height - 1],
    ]
    background = tuple(sum(color[channel] for color in corner_samples) // 4 for channel in range(3))
    non_background = 0
    bright = 0
    colors: set[tuple[int, int, int]] = set()
    for y in range(0, height, 3):
        for x in range(0, width, 3):
            color = pixels[x, y]
            delta = sum(abs(color[channel] - background[channel]) for channel in range(3))
            if delta > 18:
                non_background += 1
                colors.add((color[0] // 8, color[1] // 8, color[2] // 8))
            if sum(color) > 120:
                bright += 1
    return {
        "width": width,
        "height": height,
        "non_background_pixels": non_background,
        "bright_pixels": bright,
        "unique_sampled_colors": len(colors),
    }


if __name__ == "__main__":
    raise SystemExit(main())
