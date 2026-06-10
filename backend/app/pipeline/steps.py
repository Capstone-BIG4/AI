from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StandardStage:
    name: str
    progress: int


@dataclass(frozen=True)
class PipelineStep:
    name: str
    progress: int
    command: list[str]
    timeout: int | None = None


STANDARD_STAGES = [
    StandardStage("preprocess", 12),
    StandardStage("sam-3d-body", 28),
    StandardStage("guide-render", 44),
    StandardStage("vton-generation", 68),
    StandardStage("mask-lock-finalize", 88),
]


GPU_STEPS = [
    PipelineStep(
        "build-sam-body-base",
        18,
        ["conda", "run", "-n", "bys", "python", "scripts/18_build_sam_body_only_mannequin_base.py"],
    ),
    PipelineStep(
        "generate-front-back-vton",
        45,
        [
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            "bys",
            "python",
            "scripts/19_generate_sam_body_only_fashn_viewer.py",
            "--views",
            "front",
            "back",
            "--seeds",
            "2101",
            "--timesteps",
            "24",
            "--guidance",
            "1.65",
        ],
    ),
    PipelineStep(
        "generate-side-vton",
        70,
        [
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            "bys",
            "python",
            "scripts/19_generate_sam_body_only_fashn_viewer.py",
            "--views",
            "side",
            "--seeds",
            "2201",
            "--timesteps",
            "30",
            "--guidance",
            "1.55",
        ],
    ),
    PipelineStep(
        "mask-lock-final-viewer",
        88,
        ["conda", "run", "-n", "bys", "python", "scripts/20_select_sam_body_only_viewer.py"],
    ),
    PipelineStep(
        "verify-viewer-contract",
        96,
        ["conda", "run", "-n", "bys", "python", "scripts/10_guard_viewer_contract.py"],
    ),
]
