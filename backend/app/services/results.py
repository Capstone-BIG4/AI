from __future__ import annotations

from backend.app.core.paths import ROOT


RESULTS = {
    "tryon2d": "/assets/results/tryon-2d.png",
    "viewer": {
        "front": "/assets/results/display/sam-body-only-front-contrast.png",
        "side": "/assets/results/display/sam-body-only-side-contrast.png",
        "back": "/assets/results/display/sam-body-only-back-contrast.png",
    },
    "proof": {
        "samMeshPreview": "/assets/pipeline/sam3d/sam3d_preview_front.png",
        "frontNormal": "/assets/pipeline/guides/front_normal.png",
        "sideNormal": "/assets/pipeline/guides/side_normal.png",
        "backNormal": "/assets/pipeline/guides/back_normal.png",
        "samBodyBase": "/assets/pipeline/sam_body_only/base/front_sam_body_only_base.png",
    },
}


def asset_exists(path: str) -> bool:
    return path.startswith("/assets/") and (ROOT / path.lstrip("/")).exists()


def current_results() -> dict:
    required = [RESULTS["tryon2d"], *RESULTS["viewer"].values()]
    missing = [path for path in required if not asset_exists(path)]
    return {
        "ready": not missing,
        "missing": missing,
        "results": RESULTS,
        "manifest": "/assets/manifest.json",
    }
