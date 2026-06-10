from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from pipeline_common import ROOT


REQUIRED_FILES = [
    "frontend/index.html",
    "frontend/src/main.js",
    "frontend/src/api/client.js",
    "frontend/src/app/bootstrap.js",
    "frontend/src/app/elements.js",
    "frontend/src/components/uploads.js",
    "frontend/src/components/pipeline.js",
    "frontend/src/components/viewer.js",
    "frontend/src/components/proofGrid.js",
    "frontend/src/config/assets.js",
    "frontend/src/features/fitting/session.js",
    "frontend/src/state/runtime.js",
    "frontend/styles/app.css",
    "frontend/styles/components.css",
    "backend/app/main.py",
    "backend/app/api/router.py",
    "backend/app/api/endpoints/health.py",
    "backend/app/api/endpoints/results.py",
    "backend/app/api/endpoints/uploads.py",
    "backend/app/api/endpoints/runs.py",
    "backend/app/api/endpoints/jobs.py",
    "backend/app/pipeline/steps.py",
    "backend/app/pipeline/executor.py",
    "backend/app/services/pipeline_runner.py",
    "backend/app/services/uploads.py",
    "backend/app/services/results.py",
    "backend/app/state/jobs.py",
    "scripts/dev/run_server.py",
    "scripts/21_repair_display_viewer_assets.py",
    "assets/pipeline/env/environment-report.json",
    "assets/pipeline/env/model-access-report.json",
    "assets/pipeline/preprocessed/person_oriented.png",
    "assets/pipeline/preprocessed/person_crop.png",
    "assets/pipeline/garments/garment_metadata.json",
    "assets/pipeline/sam3d/native_output.pt",
    "assets/pipeline/sam3d/source_output_schema.json",
    "assets/pipeline/sam3d/body.ply",
    "assets/pipeline/sam3d/body_metadata.json",
    "assets/pipeline/guides/front_silhouette.png",
    "assets/pipeline/guides/front_depth.png",
    "assets/pipeline/guides/front_normal.png",
    "assets/pipeline/guides/side_silhouette.png",
    "assets/pipeline/guides/side_depth.png",
    "assets/pipeline/guides/side_normal.png",
    "assets/pipeline/guides/back_silhouette.png",
    "assets/pipeline/guides/back_depth.png",
    "assets/pipeline/guides/back_normal.png",
    "assets/pipeline/base_outputs/candidates.json",
    "assets/pipeline/refined_outputs/refinement_manifest.json",
    "assets/pipeline/viewer_hq/sam_measurements.json",
    "assets/pipeline/viewer_hq/guides/neutral_guide_manifest.json",
    "assets/pipeline/viewer_hq/candidates/candidate_manifest.json",
    "assets/pipeline/viewer_hq/refined/refined_manifest.json",
    "assets/pipeline/viewer_hq/scores.json",
    "assets/pipeline/viewer_hq/final_selection.json",
    "assets/pipeline/sam_body_only/base/sam_body_only_base_manifest.json",
    "assets/pipeline/sam_body_only/base/front_sam_body_only_base.png",
    "assets/pipeline/sam_body_only/base/side_sam_body_only_base.png",
    "assets/pipeline/sam_body_only/base/back_sam_body_only_base.png",
    "assets/pipeline/sam_body_only/fashn/sam_body_only_selection.json",
    "assets/pipeline/sam_body_only/mask_locked/mask_locked_selection.json",
    "assets/results/sam-body-only-front.png",
    "assets/results/sam-body-only-side.png",
    "assets/results/sam-body-only-back.png",
    "assets/results/display/sam-body-only-front-contrast.png",
    "assets/results/display/sam-body-only-side-contrast.png",
    "assets/results/display/sam-body-only-back-contrast.png",
    "assets/results/display/display_repair_manifest.json",
    "assets/results/sam-mannequin-front.png",
    "assets/results/sam-mannequin-side.png",
    "assets/results/sam-mannequin-back.png",
    "assets/manifest.json",
    "docs/technical-pipeline.md",
    "docs/model-cards-used.md",
]


def check_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        if im.width <= 0 or im.height <= 0:
            raise AssertionError(f"Invalid image dimensions: {path}")
        return im.width, im.height


def main() -> int:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        for path in missing:
            print(f"missing={path}")
        return 1
    for path in REQUIRED_FILES:
        full = ROOT / path
        if full.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            w, h = check_image(full)
            print(f"image={path} {w}x{h}")
        elif full.suffix.lower() == ".json":
            json.loads(full.read_text(encoding="utf-8"))
            print(f"json={path}")
        else:
            print(f"file={path}")
    print("status=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
