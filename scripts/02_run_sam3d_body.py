from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np

from pipeline_common import PIPELINE, ROOT, ensure_dir, load_env_without_printing, now_iso, redact_secret, relative, write_json


def schema_of(value, depth: int = 0):
    if depth > 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): schema_of(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [schema_of(v, depth + 1) for v in list(value)[:3]]
    if hasattr(value, "shape"):
        return {"type": type(value).__name__, "shape": list(value.shape)}
    return type(value).__name__


def save_native_output(outputs, out_path: Path) -> None:
    ensure_dir(out_path.parent)
    try:
        import torch

        torch.save(outputs, out_path)
        return
    except Exception:
        pass
    np.savez_compressed(out_path.with_suffix(".npz"), outputs=np.array([outputs], dtype=object))


def run_sam3d(input_path: Path, output_dir: Path, hf_repo_id: str) -> int:
    env = load_env_without_printing()
    secrets = [env.get("HF_TOKEN", "")]
    started_at = now_iso()
    ensure_dir(output_dir)

    metadata = {
        "source": "sam-3d-body",
        "official_repo": "https://github.com/facebookresearch/sam-3d-body",
        "hf_repo_id": hf_repo_id,
        "input_path": relative(input_path),
        "started_at": started_at,
        "status": "failed",
        "hf_token_present": bool(env.get("HF_TOKEN") or os.environ.get("HF_TOKEN")),
        "hf_token_value_printed": False,
    }

    repo = Path(env.get("SAM3D_BODY_DIR") or ROOT / "external" / "sam-3d-body").expanduser()
    if repo.exists():
        sys.path.insert(0, str(repo))
    else:
        metadata["status"] = "blocked"
        metadata["blocker"] = "SAM 3D Body source directory does not exist"
        metadata["expected_repo_path"] = str(repo)
        write_json(output_dir / "body_metadata.json", metadata)
        print("status=blocked")
        print(f"reason=SAM 3D Body source directory missing: {repo}")
        return 2

    log_path = output_dir / "sam3d_run.log"
    try:
        import cv2
        import torch
        from notebook.utils import setup_sam_3d_body
        from tools.vis_utils import visualize_sample_together

        device = "cuda" if torch.cuda.is_available() else "cpu"
        metadata["device"] = device
        metadata["torch"] = {"version": torch.__version__, "cuda_available": bool(torch.cuda.is_available())}

        estimator = setup_sam_3d_body(
            hf_repo_id=hf_repo_id,
            detector_name="",
            segmentor_name="",
            fov_name="",
            device=device,
        )
        img_bgr = cv2.imread(str(input_path))
        if img_bgr is None:
            raise RuntimeError(f"Could not read input image: {input_path}")
        outputs = estimator.process_one_image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

        native_path = output_dir / "native_output.pt"
        save_native_output(outputs, native_path)
        schema = schema_of(outputs)
        write_json(output_dir / "source_output_schema.json", {"schema": schema, "generated_at": now_iso()})

        faces = getattr(estimator, "faces", None)
        if faces is not None:
            np.save(output_dir / "estimator_faces.npy", np.asarray(faces))
            metadata["faces_path"] = relative(output_dir / "estimator_faces.npy")

        try:
            rend_img = visualize_sample_together(img_bgr, outputs, estimator.faces)
            cv2.imwrite(str(output_dir / "sam3d_preview_front.png"), rend_img.astype(np.uint8))
            metadata["preview_path"] = relative(output_dir / "sam3d_preview_front.png")
        except Exception as preview_exc:
            metadata["preview_error"] = f"{type(preview_exc).__name__}: {preview_exc}"

        metadata.update(
            {
                "status": "success",
                "completed_at": now_iso(),
                "native_output_path": relative(native_path),
                "source_output_schema_path": relative(output_dir / "source_output_schema.json"),
                "run_log_path": relative(log_path),
            }
        )
        write_json(output_dir / "body_metadata.json", metadata)
        log_path.write_text(
            "\n".join(
                [
                    "status=success",
                    f"started_at={started_at}",
                    f"completed_at={metadata['completed_at']}",
                    f"hf_repo_id={hf_repo_id}",
                    f"input_path={relative(input_path)}",
                    f"device={device}",
                    f"native_output={relative(native_path)}",
                    f"source_output_schema={relative(output_dir / 'source_output_schema.json')}",
                    "hf_token_value_printed=False",
                    "note=stdout/stderr from the successful run was not persisted by the official API wrapper; this success log replaces an earlier failed attempt log.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print("status=success")
        print("native_output=assets/pipeline/sam3d/native_output.pt")
        return 0
    except Exception as exc:
        tb = redact_secret(traceback.format_exc(), secrets)
        metadata["status"] = "blocked"
        metadata["blocker"] = f"{type(exc).__name__}: {redact_secret(str(exc), secrets)}"
        metadata["traceback_redacted_tail"] = tb[-4000:]
        metadata["completed_at"] = now_iso()
        write_json(output_dir / "body_metadata.json", metadata)
        log_path.write_text(tb, encoding="utf-8")
        print("status=blocked")
        print("body_metadata=assets/pipeline/sam3d/body_metadata.json")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(PIPELINE / "preprocessed" / "person_oriented.png"))
    parser.add_argument("--output-dir", default=str(PIPELINE / "sam3d"))
    parser.add_argument("--hf-repo-id", default="facebook/sam-3d-body-dinov3")
    args = parser.parse_args()
    return run_sam3d(Path(args.input), ensure_dir(Path(args.output_dir)), args.hf_repo_id)


if __name__ == "__main__":
    raise SystemExit(main())
