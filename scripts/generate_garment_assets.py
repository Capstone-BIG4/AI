#!/usr/bin/env python3
"""Generate MVP garment textures, templates, and a sample fitted scene."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.pipelines.garment_templates import (
    PANTS_UV_REGIONS,
    TSHIRT_UV_REGIONS,
    build_template_assets,
)
from backend.app.pipelines.garment_textures import (
    GarmentImageInputs,
    build_texture_atlas,
    generate_garment_textures,
)
from backend.app.pipelines.canonical_body import create_canonical_body_output
from backend.app.pipelines.hybrid_fitting import build_landmark_fitted_garments
from backend.app.pipelines.upright_body import create_upright_body_output


def main() -> int:
    args = parse_args()
    cloth_dir = Path(args.cloth_dir)
    garment_dir = Path(args.output_dir)
    template_root = Path(args.template_root)

    generated = generate_garment_textures(
        GarmentImageInputs(
            top_front=cloth_dir / "front.png",
            top_back=cloth_dir / "back.png" if (cloth_dir / "back.png").is_file() else None,
            pants_front=cloth_dir / "front_pants.png",
            pants_back=cloth_dir / "back_pants.png"
            if (cloth_dir / "back_pants.png").is_file()
            else None,
        ),
        garment_dir,
        texture_size=args.texture_size,
    )

    tshirt_dir = template_root / "tshirt"
    pants_dir = template_root / "pants"
    top_atlas = build_texture_atlas(
        garment_dir / "top_front.png",
        garment_dir / "top_back.png",
        tshirt_dir / "preview_texture.png",
        TSHIRT_UV_REGIONS,
        size=args.texture_size,
    )
    pants_atlas = build_texture_atlas(
        garment_dir / "pants_front.png",
        garment_dir / "pants_back.png",
        pants_dir / "preview_texture.png",
        PANTS_UV_REGIONS,
        size=args.texture_size,
    )

    tshirt_template = build_template_assets("tshirt", tshirt_dir, texture_uri="preview_texture.png")
    pants_template = build_template_assets("pants", pants_dir, texture_uri="preview_texture.png")

    fitted_report = None
    body_glb = Path(args.body_dir) / "body.glb"
    fitted_body = None
    if body_glb.is_file():
        if args.fit_body_mode == "upright":
            fitted_body = create_upright_body_output(
                args.body_dir,
                args.upright_body_dir,
                job_id=args.upright_job_id,
            )
            fit_body_dir = args.upright_body_dir
        elif args.fit_body_mode == "canonical":
            fitted_body = create_canonical_body_output(
                args.body_dir,
                args.canonical_body_dir,
                job_id=args.canonical_job_id,
            )
            fit_body_dir = args.canonical_body_dir
        elif args.fit_body_mode == "neutral":
            fit_body_dir = args.neutral_body_dir
        else:
            fit_body_dir = args.body_dir
        fitted_report = build_landmark_fitted_garments(
            body_dir=fit_body_dir,
            scene_dir=args.scene_dir,
            top_atlas=top_atlas,
            pants_atlas=pants_atlas,
            tshirt_template_dir=tshirt_dir,
            pants_template_dir=pants_dir,
        )

    print("garment_textures", generated["root"])
    print("tshirt_template", tshirt_template["root"])
    print("pants_template", pants_template["root"])
    if fitted_report is not None:
        if fitted_body is not None:
            print("fit_body", fitted_body["root"])
        print("sample_scene", args.scene_dir)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cloth-dir",
        default="assets/sample-inputs/cloth",
        help="Directory containing front/back garment product PNGs.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/garments/sample",
        help="Output directory for normalized garment textures.",
    )
    parser.add_argument(
        "--template-root",
        default="assets/templates",
        help="Output root for tshirt/pants template assets.",
    )
    parser.add_argument(
        "--body-dir",
        default="results/sam3d-body/byun/body",
        help="Source body contract directory used for fitting.",
    )
    parser.add_argument(
        "--fit-body-mode",
        choices=("neutral", "upright", "raw", "canonical"),
        default="neutral",
        help="Body used for fitting: neutral SAM/MHR mannequin, SAM-proportion fitting mannequin, upright SAM mesh, or raw SAM mesh.",
    )
    parser.add_argument(
        "--neutral-body-dir",
        default="results/neutral-body/byun/body",
        help="Neutral SAM/MHR mannequin contract directory used for fitting.",
    )
    parser.add_argument(
        "--upright-body-dir",
        default="results/upright-body/byun/body",
        help="Output body contract directory for the reoriented SAM mesh used by the viewer.",
    )
    parser.add_argument(
        "--upright-job-id",
        default="byun-upright-body",
        help="Job id written to upright body metadata.",
    )
    parser.add_argument(
        "--canonical-body-dir",
        default="results/canonical-body/byun/body",
        help="Output body contract directory for the SAM-proportion fitting mannequin.",
    )
    parser.add_argument(
        "--canonical-job-id",
        default="byun-canonical-body",
        help="Job id written to the canonical body metadata.",
    )
    parser.add_argument(
        "--scene-dir",
        default="results/fitted/byun/scene",
        help="Output directory for sample fitted garment GLBs.",
    )
    parser.add_argument(
        "--texture-size",
        type=int,
        default=1024,
        help="Square texture size in pixels.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
