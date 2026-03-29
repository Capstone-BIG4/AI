from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import ReconstructionSettings, Sam3DSettings
from app.pipelines.reconstruction import ReconstructionPipeline
from app.providers import MockReconstructionProvider, Sam3DBodyProvider


def add_sam3d_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sam3d-repo-path", default=None, help="Path to official SAM 3D Body repo checkout")
    parser.add_argument("--sam3d-checkpoint-path", default=None, help="Path to model.ckpt")
    parser.add_argument("--sam3d-mhr-path", default=None, help="Path to mhr_model.pt")
    parser.add_argument("--sam3d-hf-repo-id", default=None, help="Hugging Face repo id fallback")
    parser.add_argument("--sam3d-device", default=None, help="auto, cuda, or cpu")
    parser.add_argument("--sam3d-detector-name", default=None, help="vitdet, sam3, or none")
    parser.add_argument("--sam3d-segmentor-name", default=None, help="sam2, sam3, or none")
    parser.add_argument("--sam3d-fov-name", default=None, help="moge2 or none")
    parser.add_argument("--sam3d-detector-path", default=None, help="Optional detector weights directory")
    parser.add_argument("--sam3d-segmentor-path", default=None, help="Optional segmentor root directory")
    parser.add_argument("--sam3d-fov-path", default=None, help="Optional fov model path or repo")
    parser.add_argument("--sam3d-bbox-thresh", type=float, default=None, help="Official detector bbox threshold")
    parser.add_argument("--sam3d-person-selection", default=None, help="largest_bbox, largest_mesh, or first")
    parser.add_argument("--sam3d-use-mask", action="store_true", default=None, help="Enable mask-conditioned inference")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Step 3 reconstruction CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run reconstruction for a single image")
    run_parser.add_argument("--input", required=True, help="Input image path")
    run_parser.add_argument("--output-root", required=True, help="Output root directory")
    run_parser.add_argument("--provider", default="mock", choices=["mock", "sam3d"])
    run_parser.add_argument("--run-id", default=None, help="Optional fixed run id")
    add_sam3d_arguments(run_parser)

    manifest_parser = subparsers.add_parser("run-manifest", help="Run reconstruction for a manifest CSV")
    manifest_parser.add_argument("--manifest", required=True, help="Manifest CSV path")
    manifest_parser.add_argument("--image-root", required=True, help="Image root directory")
    manifest_parser.add_argument("--output-root", required=True, help="Output root directory")
    manifest_parser.add_argument("--provider", default="mock", choices=["mock", "sam3d"])
    manifest_parser.add_argument("--run-id", default=None, help="Optional fixed run id")
    add_sam3d_arguments(manifest_parser)

    providers_parser = subparsers.add_parser("providers", help="List available providers")
    providers_parser.add_argument("--provider", default=None, choices=["mock", "sam3d"], help="Optional provider detail")
    add_sam3d_arguments(providers_parser)
    return parser


def build_sam3d_settings(args: argparse.Namespace) -> Sam3DSettings:
    return Sam3DSettings.from_env().with_overrides(
        repo_path=args.sam3d_repo_path,
        checkpoint_path=args.sam3d_checkpoint_path,
        mhr_path=args.sam3d_mhr_path,
        hf_repo_id=args.sam3d_hf_repo_id,
        device=args.sam3d_device,
        detector_name=args.sam3d_detector_name,
        segmentor_name=args.sam3d_segmentor_name,
        fov_name=args.sam3d_fov_name,
        detector_path=args.sam3d_detector_path,
        segmentor_path=args.sam3d_segmentor_path,
        fov_path=args.sam3d_fov_path,
        bbox_thresh=args.sam3d_bbox_thresh,
        use_mask=args.sam3d_use_mask,
        person_selection=args.sam3d_person_selection,
    )


def create_provider(name: str, args: argparse.Namespace):
    if name == "mock":
        return MockReconstructionProvider()
    if name == "sam3d":
        return Sam3DBodyProvider(settings=build_sam3d_settings(args))
    raise ValueError(f"unsupported provider: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "providers":
        detail = args.provider
        if detail in {None, "mock"}:
            print("mock: synthetic reconstruction provider for local Step 3 smoke validation")
        if detail in {None, "sam3d"}:
            provider = create_provider("sam3d", args)
            print(json.dumps(provider.readiness_report(), indent=2, ensure_ascii=True))
        return 0

    provider = create_provider(args.provider, args)
    pipeline = ReconstructionPipeline(settings=ReconstructionSettings(), provider=provider)

    if args.command == "run":
        result = pipeline.run_single(
            input_path=Path(args.input),
            output_root=Path(args.output_root),
            run_id=args.run_id,
        )
        print(result.model_dump_json(indent=2))
        return 0

    if args.command == "run-manifest":
        summary = pipeline.run_manifest(
            manifest_path=Path(args.manifest),
            image_root=Path(args.image_root),
            output_root=Path(args.output_root),
            run_id=args.run_id,
        )
        print(summary.model_dump_json(indent=2))
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
