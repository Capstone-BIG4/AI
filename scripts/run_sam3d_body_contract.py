#!/usr/bin/env python3
"""Run SAM 3D Body and export the project body contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.pipelines.sam3d_body_contract import (
    export_neutral_sam3d_body_contract,
    export_sam3d_body_contract,
)


def main() -> int:
    args = parse_args()
    sam_repo = resolve_path(args.sam_repo)
    checkpoint_path = resolve_path(args.checkpoint_path)
    mhr_path = resolve_path(args.mhr_path)
    image_path = resolve_path(args.image)
    output_dir = resolve_path(args.output_dir)

    for path, label in (
        (sam_repo, "SAM 3D Body repo"),
        (checkpoint_path, "checkpoint"),
        (mhr_path, "MHR model"),
        (image_path, "input image"),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Missing {label}: {path}")

    sys.path.insert(0, str(sam_repo))

    import torch
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body

    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    if args.require_cuda and device.type != "cuda":
        raise RuntimeError("CUDA is required but not available")

    model, model_cfg = load_sam_3d_body(
        str(checkpoint_path),
        device=device,
        mhr_path=str(mhr_path),
    )

    estimator = SAM3DBodyEstimator(
        sam_3d_body_model=model,
        model_cfg=model_cfg,
        human_detector=None,
        human_segmentor=None,
        fov_estimator=None,
    )

    outputs = estimator.process_one_image(str(image_path), inference_type=args.inference_type)
    if not outputs:
        raise RuntimeError(f"SAM 3D Body produced no person outputs for {image_path}")

    result = export_sam3d_body_contract(
        person_output=outputs[0],
        faces=estimator.faces,
        output_dir=output_dir,
        job_id=args.job_id,
        model_name="sam-3d-body",
        model_version=args.model_version,
        warnings=[] if len(outputs) == 1 else ["multiple_people_detected_first_used"],
    )
    print(f"Exported body contract: {result['root']}")
    if args.neutral_output_dir:
        neutral = export_neutral_sam3d_body_contract(
            person_output=outputs[0],
            model_head=model.head_pose,
            faces=estimator.faces,
            output_dir=resolve_path(args.neutral_output_dir),
            job_id=args.neutral_job_id,
            model_name="sam-3d-body-neutral-mannequin",
            model_version=args.model_version,
            warnings=[] if len(outputs) == 1 else ["multiple_people_detected_first_used"],
        )
        print(f"Exported neutral body contract: {neutral['root']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Input full-body image path.")
    parser.add_argument(
        "--output-dir",
        default="results/sam3d-body/contract/body",
        help="Directory where body.glb/landmarks.json/body_metadata.json are written.",
    )
    parser.add_argument(
        "--sam-repo",
        default="external/sam-3d-body",
        help="Local facebookresearch/sam-3d-body clone path.",
    )
    parser.add_argument(
        "--checkpoint-path",
        default="checkpoints/sam-3d-body-dinov3/model.ckpt",
        help="SAM 3D Body checkpoint path.",
    )
    parser.add_argument(
        "--mhr-path",
        default="checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt",
        help="MHR model path.",
    )
    parser.add_argument("--job-id", default="sam3d-body-contract")
    parser.add_argument(
        "--neutral-output-dir",
        default="",
        help="Optional output directory for a neutral-pose SAM/MHR mannequin body.",
    )
    parser.add_argument("--neutral-job-id", default="sam3d-body-neutral-contract")
    parser.add_argument("--model-version", default="dinov3")
    parser.add_argument("--inference-type", default="body", choices=("body", "full"))
    parser.add_argument(
        "--allow-cpu",
        action="store_false",
        dest="require_cuda",
        help="Allow CPU execution. Not recommended for normal SAM 3D Body runs.",
    )
    parser.set_defaults(require_cuda=True)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


if __name__ == "__main__":
    raise SystemExit(main())
