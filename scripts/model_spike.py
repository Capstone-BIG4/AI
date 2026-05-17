#!/usr/bin/env python3
"""Run the phase-0 SAM 3D Body environment spike.

The script is intentionally safe by default: it inspects local prerequisites,
creates the phase-0 fallback body contract, and writes docs/model-spike.md.
It only runs the real SAM 3D Body demo when --run-sam is provided.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.pipelines.fallback_body import create_fallback_body_output


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def main() -> int:
    args = parse_args()

    output_root = resolve_path(args.output_root)
    body_output_dir = output_root / args.job_id / "body"
    report_path = resolve_path(args.report)
    sam_repo = resolve_path(args.sam_repo)
    checkpoint_path = resolve_path(args.checkpoint_path)
    mhr_path = resolve_path(args.mhr_path)
    sample_image_dir = resolve_path(args.sample_image_dir)

    checks = collect_checks(
        sam_repo=sam_repo,
        checkpoint_path=checkpoint_path,
        mhr_path=mhr_path,
        sample_image_dir=sample_image_dir,
    )

    fallback_result = None
    if args.create_fallback:
        fallback_result = create_fallback_body_output(
            body_output_dir,
            job_id=args.job_id,
            warnings=["real_sam_3d_body_not_executed"],
        )

    sam_run_result = None
    if args.run_sam:
        sam_run_result = run_sam_demo(
            sam_repo=sam_repo,
            checkpoint_path=checkpoint_path,
            mhr_path=mhr_path,
            sample_image_dir=sample_image_dir,
            output_root=output_root / args.job_id / "sam-raw",
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(
            checks=checks,
            sam_repo=sam_repo,
            checkpoint_path=checkpoint_path,
            mhr_path=mhr_path,
            sample_image_dir=sample_image_dir,
            output_root=output_root,
            body_output_dir=body_output_dir,
            fallback_result=fallback_result,
            sam_run_result=sam_run_result,
            run_sam=args.run_sam,
        ),
        encoding="utf-8",
    )

    print(f"Wrote model spike report: {report_path}")
    if fallback_result is not None:
        print(f"Wrote fallback body contract: {body_output_dir}")

    real_sam_ready = all(
        check.ok
        for check in checks
        if check.name
        in {
            "sam_repo",
            "checkpoint",
            "mhr_model",
            "sample_images",
        }
    )
    if args.strict and not real_sam_ready:
        print("Strict mode failed: real SAM 3D Body prerequisites are incomplete.")
        return 2
    if args.run_sam and sam_run_result is not None and sam_run_result.status != "ok":
        return 3
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sam-repo",
        default=os.environ.get("SAM3D_BODY_REPO", "external/sam-3d-body"),
        help="Local facebookresearch/sam-3d-body clone path.",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=os.environ.get(
            "SAM3D_CHECKPOINT_PATH",
            "checkpoints/sam-3d-body-dinov3/model.ckpt",
        ),
        help="SAM 3D Body checkpoint path.",
    )
    parser.add_argument(
        "--mhr-path",
        default=os.environ.get(
            "SAM3D_MHR_PATH",
            "checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt",
        ),
        help="MHR model path.",
    )
    parser.add_argument(
        "--sample-image-dir",
        default="assets/sample-inputs/body",
        help="Directory containing sample full-body input images.",
    )
    parser.add_argument(
        "--output-root",
        default="results/spike",
        help="Directory for spike outputs.",
    )
    parser.add_argument(
        "--job-id",
        default="phase0-fallback",
        help="Job id used for generated contract outputs.",
    )
    parser.add_argument(
        "--report",
        default="docs/model-spike.md",
        help="Markdown report path.",
    )
    parser.add_argument(
        "--run-sam",
        action="store_true",
        help="Run the real SAM 3D Body demo.py. Off by default.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_false",
        dest="create_fallback",
        help="Do not create fallback body contract outputs.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when real SAM prerequisites are incomplete.",
    )
    parser.set_defaults(create_fallback=True)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def collect_checks(
    *,
    sam_repo: Path,
    checkpoint_path: Path,
    mhr_path: Path,
    sample_image_dir: Path,
) -> list[CheckResult]:
    checks = [
        CheckResult("python", "ok", sys.version.replace("\n", " ")),
        check_python_version(),
        check_module("torch"),
        check_torch_cuda(),
        check_nvidia_smi(),
        check_hf_auth(),
        check_sam_repo(sam_repo),
        check_sam_python_import(sam_repo),
        check_file("checkpoint", checkpoint_path),
        check_file("mhr_model", mhr_path),
        check_sample_images(sample_image_dir),
    ]
    return checks


def check_python_version() -> CheckResult:
    current = sys.version_info
    if current.major == 3 and current.minor == 11:
        return CheckResult("python_expected", "ok", "Python 3.11 matches upstream install guide.")
    return CheckResult(
        "python_expected",
        "warn",
        f"Current Python is {current.major}.{current.minor}; upstream install guide uses Python 3.11.",
    )


def check_module(name: str) -> CheckResult:
    spec = importlib.util.find_spec(name)
    if spec is None:
        return CheckResult(name, "missing", f"Python module {name!r} is not importable.")
    return CheckResult(name, "ok", f"Python module {name!r} is importable.")


def check_torch_cuda() -> CheckResult:
    try:
        import torch  # type: ignore
    except Exception as exc:
        return CheckResult("torch_cuda", "missing", f"torch import failed: {exc}")

    if not torch.cuda.is_available():
        return CheckResult(
            "torch_cuda",
            "missing",
            f"torch {torch.__version__} is installed, but CUDA is not available.",
        )

    device_count = torch.cuda.device_count()
    names = [torch.cuda.get_device_name(i) for i in range(device_count)]
    return CheckResult(
        "torch_cuda",
        "ok",
        f"torch {torch.__version__}, CUDA {torch.version.cuda}, devices: {names}",
    )


def check_nvidia_smi() -> CheckResult:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        return CheckResult("nvidia_smi", "missing", "nvidia-smi is not installed.")
    except subprocess.TimeoutExpired:
        return CheckResult("nvidia_smi", "missing", "nvidia-smi timed out.")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return CheckResult("nvidia_smi", "missing", detail or "nvidia-smi failed.")
    return CheckResult("nvidia_smi", "ok", result.stdout.strip())


def check_hf_auth() -> CheckResult:
    try:
        result = subprocess.run(
            ["hf", "auth", "whoami"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        return CheckResult("hf_auth", "missing", "hf CLI is not installed.")
    except subprocess.TimeoutExpired:
        return CheckResult("hf_auth", "missing", "hf auth check timed out.")

    if result.returncode == 0:
        user = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "ok"
        return CheckResult("hf_auth", "ok", f"Hugging Face auth active for {user}.")

    detail = (result.stderr or result.stdout).strip().splitlines()[0]
    return CheckResult("hf_auth", "missing", detail)


def check_sam_repo(path: Path) -> CheckResult:
    demo = path / "demo.py"
    install = path / "INSTALL.md"
    if demo.is_file() and install.is_file():
        return CheckResult("sam_repo", "ok", f"Found SAM 3D Body repo at {path}")
    return CheckResult(
        "sam_repo",
        "missing",
        f"Expected demo.py and INSTALL.md under {path}",
    )


def check_sam_python_import(path: Path) -> CheckResult:
    if not path.is_dir():
        return CheckResult("sam_python_import", "missing", f"Repo path not found: {path}")

    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            f"sys.path.insert(0, {str(path)!r}); "
            "import sam_3d_body; "
            "print('ok')"
        ),
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode == 0:
        return CheckResult("sam_python_import", "ok", "sam_3d_body imports from local repo.")
    detail = (result.stderr or result.stdout).strip().splitlines()[-1]
    return CheckResult("sam_python_import", "missing", detail)


def check_file(name: str, path: Path) -> CheckResult:
    if path.is_file():
        return CheckResult(name, "ok", f"Found {path}")
    return CheckResult(name, "missing", f"Missing {path}")


def check_sample_images(path: Path) -> CheckResult:
    images = list_sample_images(path)
    if images:
        return CheckResult(
            "sample_images",
            "ok",
            f"Found {len(images)} sample image(s) under {path}",
        )
    return CheckResult(
        "sample_images",
        "missing",
        f"No sample images found under {path}",
    )


def list_sample_images(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
    )


def run_sam_demo(
    *,
    sam_repo: Path,
    checkpoint_path: Path,
    mhr_path: Path,
    sample_image_dir: Path,
    output_root: Path,
) -> CheckResult:
    command = [
        sys.executable,
        str(sam_repo / "demo.py"),
        "--image_folder",
        str(sample_image_dir),
        "--output_folder",
        str(output_root),
        "--checkpoint_path",
        str(checkpoint_path),
        "--mhr_path",
        str(mhr_path),
    ]
    output_root.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=sam_repo,
        text=True,
        capture_output=True,
        timeout=60 * 60,
        check=False,
    )
    elapsed = time.perf_counter() - started
    log_path = output_root / "demo-command.log"
    log_path.write_text(
        "Command:\n"
        + " ".join(command)
        + "\n\nSTDOUT:\n"
        + result.stdout
        + "\n\nSTDERR:\n"
        + result.stderr,
        encoding="utf-8",
    )

    if result.returncode == 0:
        return CheckResult(
            "sam_demo",
            "ok",
            f"demo.py completed in {elapsed:.1f}s; log: {log_path}",
        )
    return CheckResult(
        "sam_demo",
        "missing",
        f"demo.py failed with code {result.returncode}; log: {log_path}",
    )


def render_report(
    *,
    checks: Iterable[CheckResult],
    sam_repo: Path,
    checkpoint_path: Path,
    mhr_path: Path,
    sample_image_dir: Path,
    output_root: Path,
    body_output_dir: Path,
    fallback_result: dict[str, object] | None,
    sam_run_result: CheckResult | None,
    run_sam: bool,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    rows = "\n".join(
        f"| `{check.name}` | {check.status} | {markdown_cell(check.detail)} |"
        for check in checks
    )
    fallback_section = render_fallback_section(body_output_dir, fallback_result)
    sam_section = render_sam_run_section(run_sam, sam_run_result)

    return f"""# Phase 0 Model Spike Report

Generated at: `{generated_at}`

## Purpose

This report checks whether the local environment is ready to run SAM 3D Body and
whether the project can already produce the phase-0 body output contract:

```text
body.glb
landmarks.json
body_metadata.json
```

## Paths

- SAM 3D Body repo: `{sam_repo}`
- Checkpoint path: `{checkpoint_path}`
- MHR model path: `{mhr_path}`
- Sample image dir: `{sample_image_dir}`
- Output root: `{output_root}`

## Environment Checks

| Check | Status | Detail |
| --- | --- | --- |
{rows}

{fallback_section}

{sam_section}

## Current Verdict

{render_verdict(checks, fallback_result, sam_run_result)}

## Next Actions

{render_next_actions(checks, sam_run_result)}
"""


def render_fallback_section(
    body_output_dir: Path,
    fallback_result: dict[str, object] | None,
) -> str:
    if fallback_result is None:
        return "## Fallback Body Contract\n\nFallback generation was skipped.\n"
    return f"""## Fallback Body Contract

Status: `ok`

Output directory:

```text
{body_output_dir}
```

Generated files:

- `body.glb`
- `landmarks.json`
- `body_metadata.json`

This is a development fallback only. It must not be presented as SAM 3D Body
reconstruction output.
"""


def render_sam_run_section(
    run_sam: bool,
    sam_run_result: CheckResult | None,
) -> str:
    if not run_sam:
        return """## Real SAM 3D Body Demo Run

Status: `skipped`

The real demo is not run unless `--run-sam` is passed.
"""
    if sam_run_result is None:
        return "## Real SAM 3D Body Demo Run\n\nStatus: `not_run`\n"
    return f"""## Real SAM 3D Body Demo Run

Status: `{sam_run_result.status}`

{sam_run_result.detail}
"""


def render_verdict(
    checks: Iterable[CheckResult],
    fallback_result: dict[str, object] | None,
    sam_run_result: CheckResult | None,
) -> str:
    check_map = {check.name: check for check in checks}
    missing_real = [
        name
        for name in ("sam_repo", "checkpoint", "mhr_model", "sample_images")
        if not check_map[name].ok
    ]

    lines: list[str] = []
    if not missing_real:
        lines.append("- Real SAM 3D Body prerequisites are present.")
    else:
        lines.append(
            "- Real SAM 3D Body inference is blocked by: "
            + ", ".join(f"`{name}`" for name in missing_real)
            + "."
        )

    if fallback_result is not None:
        lines.append("- Fallback body output contract generation is working.")
    else:
        lines.append("- Fallback body output contract generation was not executed.")
    if sam_run_result is not None and sam_run_result.ok:
        lines.append("- Real SAM 3D Body demo execution is working.")

    return "\n".join(lines)


def render_next_actions(
    checks: Iterable[CheckResult],
    sam_run_result: CheckResult | None,
) -> str:
    check_map = {check.name: check for check in checks}
    missing = [
        name
        for name in ("hf_auth", "checkpoint", "mhr_model", "sample_images")
        if name in check_map and not check_map[name].ok
    ]
    if missing:
        return "\n".join(
            [
                "1. Fix the missing gate(s): "
                + ", ".join(f"`{name}`" for name in missing)
                + ".",
                "2. Re-run:",
                "",
                "```bash",
                "conda run -n bys python scripts/model_spike.py --run-sam --strict",
                "```",
            ]
        )
    if sam_run_result is None or not sam_run_result.ok:
        return "\n".join(
            [
                "1. Run the real SAM demo gate:",
                "",
                "```bash",
                "conda run -n bys python scripts/model_spike.py --run-sam --strict",
                "```",
            ]
        )
    return "\n".join(
        [
            "1. Export the project body contract:",
            "",
            "```bash",
            "conda run -n bys python scripts/run_sam3d_body_contract.py \\",
            "  --image assets/sample-inputs/body/dancing.jpg \\",
            "  --output-dir results/sam3d-body/dancing/body",
            "```",
            "2. Continue with the Milestone 1 viewer and garment template work.",
        ]
    )


def markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
