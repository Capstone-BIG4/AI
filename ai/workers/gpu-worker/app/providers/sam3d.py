from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from app.config import Sam3DSettings
from app.models import ValidationResult
from app.providers.base import BaseReconstructionProvider, ProviderOutput

try:
    import torch
except Exception:  # pragma: no cover - optional dependency path
    torch = None


@dataclass
class Sam3DBodyProvider(BaseReconstructionProvider):
    settings: Sam3DSettings = field(default_factory=Sam3DSettings.from_env)
    name: str = "sam3d"
    version: str = "sam3d-official-adapter-v1"
    _estimator: Any = field(default=None, init=False, repr=False)
    _faces: np.ndarray | None = field(default=None, init=False, repr=False)
    _keypoint_names: list[str] = field(default_factory=list, init=False, repr=False)

    def readiness_report(self) -> dict[str, Any]:
        repo_path = Path(self.settings.repo_path).resolve()
        checkpoint_path = Path(self.settings.checkpoint_path).resolve() if self.settings.checkpoint_path else None
        mhr_path = Path(self.settings.mhr_path).resolve() if self.settings.mhr_path else None
        detector_name = self._normalize_component_name(self.settings.detector_name)
        segmentor_name = self._normalize_component_name(self.settings.segmentor_name)
        fov_name = self._normalize_component_name(self.settings.fov_name)

        issues: list[str] = []
        warnings: list[str] = []
        missing_modules: list[str] = []

        if not repo_path.exists():
            issues.append("official repo path missing")

        if checkpoint_path is not None and not checkpoint_path.exists():
            issues.append("checkpoint path missing")

        if mhr_path is not None and not mhr_path.exists():
            issues.append("mhr path missing")

        if not self._has_local_checkpoint_source() and not self.settings.hf_repo_id:
            issues.append("checkpoint source missing")

        if self.settings.device == "cuda" and not self._cuda_available():
            issues.append("cuda requested but unavailable")
        elif self.settings.device in {"auto", "cpu"} and not self._cuda_available():
            warnings.append("cuda unavailable, cpu fallback only")

        for module_name in self._required_core_modules():
            if not self._module_available(module_name):
                missing_modules.append(module_name)

        if detector_name == "vitdet" and not self._module_available("detectron2"):
            warnings.append("detectron2 missing, vitdet detector unavailable")
        if detector_name == "sam3" and not self._module_available("sam3"):
            warnings.append("sam3 package missing, sam3 detector unavailable")

        if segmentor_name == "sam2":
            if not self.settings.segmentor_path:
                warnings.append("segmentor path empty, sam2 segmentor disabled")
            elif not self._module_available("sam2"):
                warnings.append("sam2 package missing, sam2 segmentor unavailable")
        if segmentor_name == "sam3" and not self._module_available("sam3"):
            warnings.append("sam3 package missing, sam3 segmentor unavailable")

        if fov_name == "moge2" and not self._module_available("moge"):
            warnings.append("moge package missing, moge2 fov estimator unavailable")

        core_import_error = None
        if repo_path.exists():
            try:
                self._import_core(check_only=True)
            except Exception as exc:  # pragma: no cover - environment-dependent branch
                core_import_error = f"{type(exc).__name__}: {exc}"
                issues.append("official core import failed")

        if missing_modules:
            warnings.append("missing core python modules: " + ", ".join(sorted(set(missing_modules))))

        status = "ready"
        if issues:
            status = "blocked"
        elif warnings:
            status = "warning"

        return {
            "status": status,
            "provider": self.name,
            "adapter_version": self.version,
            "official_repo_path": str(repo_path),
            "official_repo_present": repo_path.exists(),
            "checkpoint_path": str(checkpoint_path) if checkpoint_path else "",
            "checkpoint_present": checkpoint_path.exists() if checkpoint_path else False,
            "mhr_path": str(mhr_path) if mhr_path else "",
            "mhr_present": mhr_path.exists() if mhr_path else False,
            "hf_repo_id": self.settings.hf_repo_id,
            "device_request": self.settings.device,
            "cuda_available": self._cuda_available(),
            "bbox_thresh": self.settings.bbox_thresh,
            "use_mask": self.settings.use_mask,
            "detector_name": detector_name or "",
            "segmentor_name": segmentor_name or "",
            "fov_name": fov_name or "",
            "person_selection": self.settings.person_selection,
            "issues": issues,
            "warnings": warnings,
            "core_import_error": core_import_error,
            "official_sources": {
                "repo_readme": "ai/third_party/sam-3d-body/README.md",
                "repo_install": "ai/third_party/sam-3d-body/INSTALL.md",
                "repo_demo": "ai/third_party/sam-3d-body/demo.py",
            },
        }

    def run(self, image: Image.Image, sample_id: str, validation: ValidationResult) -> ProviderOutput:
        estimator = self._get_estimator()
        image_rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        outputs = estimator.process_one_image(
            image_rgb,
            bbox_thr=self.settings.bbox_thresh,
            use_mask=self.settings.use_mask,
        )

        if len(outputs) == 0:
            raise RuntimeError("SAM 3D Body returned no detected humans for the input image")

        selected_index, selected_output = self._select_output(outputs)
        mask_image = self._build_mask_image(
            mask=selected_output.get("mask"),
            bbox=selected_output.get("bbox"),
            width=image.width,
            height=image.height,
        )
        masked_preview = self._build_masked_preview(image=image, mask_image=mask_image)
        keypoints = self._serialize_keypoints(selected_output)
        body_params = self._serialize_body_params(selected_output, selected_index=selected_index)
        raw_mesh_obj = self._mesh_to_obj(vertices=selected_output["pred_vertices"], faces=self._faces)

        quality_scores = {
            "validation_score": round({"pass": 0.92, "warning": 0.71, "reject": 0.2}[validation.decision], 4),
            "bbox_area_ratio": round(self._bbox_area_ratio(selected_output.get("bbox"), image.width, image.height), 4),
            "mask_coverage_ratio": round(self._mask_coverage_ratio(mask_image), 4),
            "reconstruction_score": round(self._reconstruction_score(validation, selected_output, mask_image, image.width, image.height), 4),
        }

        return ProviderOutput(
            mask_image=mask_image,
            masked_preview_image=masked_preview,
            keypoints=keypoints,
            body_params=body_params,
            raw_mesh_obj=raw_mesh_obj,
            quality_scores=quality_scores,
            notes=[
                f"official repo path: {Path(self.settings.repo_path).resolve()}",
                f"person selection: {self.settings.person_selection}",
                f"selected person index: {selected_index}",
            ],
        )

    def _get_estimator(self) -> Any:
        if self._estimator is not None:
            return self._estimator

        report = self.readiness_report()
        if report["status"] == "blocked":
            raise RuntimeError("SAM 3D Body readiness blocked: " + "; ".join(report["issues"]))

        core = self._import_core(check_only=False)
        load_sam_3d_body = core["load_sam_3d_body"]
        SAM3DBodyEstimator = core["SAM3DBodyEstimator"]
        HumanDetector = core["HumanDetector"]
        HumanSegmentor = core["HumanSegmentor"]
        FOVEstimator = core["FOVEstimator"]
        pose_info = core["pose_info"]

        device = self._resolve_device()
        checkpoint_path, mhr_path = self._resolve_checkpoint_source(load_sam_3d_body=load_sam_3d_body)
        model, model_cfg = load_sam_3d_body(
            checkpoint_path=checkpoint_path,
            device=device,
            mhr_path=mhr_path,
        )

        detector = None
        detector_name = self._normalize_component_name(self.settings.detector_name)
        if detector_name:
            detector = HumanDetector(
                name=detector_name,
                device=device,
                path=self.settings.detector_path,
            )

        segmentor = None
        segmentor_name = self._normalize_component_name(self.settings.segmentor_name)
        segmentor_path = self.settings.segmentor_path.strip()
        if segmentor_name and ((segmentor_name == "sam2" and segmentor_path) or segmentor_name != "sam2"):
            segmentor = HumanSegmentor(
                name=segmentor_name,
                device=device,
                path=segmentor_path,
            )

        fov_estimator = None
        fov_name = self._normalize_component_name(self.settings.fov_name)
        if fov_name:
            fov_estimator = FOVEstimator(
                name=fov_name,
                device=device,
                path=self.settings.fov_path,
            )

        self._estimator = SAM3DBodyEstimator(
            sam_3d_body_model=model,
            model_cfg=model_cfg,
            human_detector=detector,
            human_segmentor=segmentor,
            fov_estimator=fov_estimator,
        )
        self._faces = np.asarray(self._estimator.faces)
        self._keypoint_names = [
            item["name"]
            for _, item in sorted(pose_info["keypoint_info"].items(), key=lambda entry: entry[0])
        ]

        sam3d_module = core["sam3d_module"]
        self.version = f"sam3d-official-{getattr(sam3d_module, '__version__', 'unknown')}"
        return self._estimator

    def _import_core(self, check_only: bool = False) -> dict[str, Any]:
        repo_path = Path(self.settings.repo_path).resolve()
        if not repo_path.exists():
            raise FileNotFoundError(f"official repo path missing: {repo_path}")

        repo_str = str(repo_path)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

        sam3d_module = importlib.import_module("sam_3d_body")
        if check_only:
            return {"sam3d_module": sam3d_module}

        HumanDetector = None
        HumanSegmentor = None
        FOVEstimator = None

        detector_name = self._normalize_component_name(self.settings.detector_name)
        segmentor_name = self._normalize_component_name(self.settings.segmentor_name)
        fov_name = self._normalize_component_name(self.settings.fov_name)

        if detector_name:
            HumanDetector = importlib.import_module("tools.build_detector").HumanDetector
        if segmentor_name and ((segmentor_name == "sam2" and self.settings.segmentor_path.strip()) or segmentor_name != "sam2"):
            HumanSegmentor = importlib.import_module("tools.build_sam").HumanSegmentor
        if fov_name:
            FOVEstimator = importlib.import_module("tools.build_fov_estimator").FOVEstimator

        pose_info = importlib.import_module("sam_3d_body.metadata.mhr70").pose_info

        return {
            "sam3d_module": sam3d_module,
            "load_sam_3d_body": sam3d_module.load_sam_3d_body,
            "SAM3DBodyEstimator": sam3d_module.SAM3DBodyEstimator,
            "HumanDetector": HumanDetector,
            "HumanSegmentor": HumanSegmentor,
            "FOVEstimator": FOVEstimator,
            "pose_info": pose_info,
        }

    def _resolve_checkpoint_source(self, load_sam_3d_body: Any) -> tuple[str, str]:
        checkpoint_path = self.settings.checkpoint_path.strip()
        mhr_path = self.settings.mhr_path.strip()
        if checkpoint_path and mhr_path:
            return checkpoint_path, mhr_path

        hf_repo_id = self.settings.hf_repo_id.strip()
        if not hf_repo_id:
            raise RuntimeError("SAM 3D Body checkpoint source missing: local checkpoint or hf repo id required")

        if not self._module_available("huggingface_hub"):
            raise RuntimeError("huggingface_hub missing for hf checkpoint download")

        from huggingface_hub import snapshot_download

        local_dir = snapshot_download(repo_id=hf_repo_id)
        resolved_checkpoint = Path(local_dir) / "model.ckpt"
        resolved_mhr = Path(local_dir) / "assets" / "mhr_model.pt"
        if not resolved_checkpoint.exists() or not resolved_mhr.exists():
            raise RuntimeError("SAM 3D Body hf snapshot missing expected checkpoint or mhr assets")
        return str(resolved_checkpoint), str(resolved_mhr)

    def _select_output(self, outputs: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        if len(outputs) == 1:
            return 0, outputs[0]

        if self.settings.person_selection == "largest_mesh":
            scores = []
            for output in outputs:
                vertices = np.asarray(output["pred_vertices"])
                extents = np.ptp(vertices, axis=0)
                scores.append(float(extents[0] + extents[1]))
            index = int(np.argmax(scores))
            return index, outputs[index]

        scores = []
        for output in outputs:
            bbox = np.asarray(output["bbox"], dtype=np.float32)
            width = max(float(bbox[2] - bbox[0]), 0.0)
            height = max(float(bbox[3] - bbox[1]), 0.0)
            scores.append(width * height)
        index = int(np.argmax(scores))
        return index, outputs[index]

    def _serialize_keypoints(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        keypoints_2d = np.asarray(output.get("pred_keypoints_2d", []), dtype=np.float32)
        keypoints_3d = np.asarray(output.get("pred_keypoints_3d", []), dtype=np.float32)
        count = max(len(keypoints_2d), len(keypoints_3d))
        if not self._keypoint_names:
            self._keypoint_names = [f"joint_{idx:03d}" for idx in range(count)]

        result: list[dict[str, Any]] = []
        for idx in range(count):
            row: dict[str, Any] = {
                "index": idx,
                "name": self._keypoint_names[idx] if idx < len(self._keypoint_names) else f"joint_{idx:03d}",
            }
            if idx < len(keypoints_2d):
                row["x"] = round(float(keypoints_2d[idx][0]), 4)
                row["y"] = round(float(keypoints_2d[idx][1]), 4)
            if idx < len(keypoints_3d):
                row["x3d"] = round(float(keypoints_3d[idx][0]), 6)
                row["y3d"] = round(float(keypoints_3d[idx][1]), 6)
                row["z3d"] = round(float(keypoints_3d[idx][2]), 6)
            result.append(row)
        return result

    def _serialize_body_params(self, output: dict[str, Any], selected_index: int) -> dict[str, Any]:
        return {
            "source": "sam3d-body-official",
            "selected_person_index": selected_index,
            "bbox": self._to_python(output.get("bbox")),
            "focal_length": self._to_python(output.get("focal_length")),
            "pred_cam_t": self._to_python(output.get("pred_cam_t")),
            "pred_pose_raw": self._to_python(output.get("pred_pose_raw")),
            "global_rot": self._to_python(output.get("global_rot")),
            "body_pose_params": self._to_python(output.get("body_pose_params")),
            "hand_pose_params": self._to_python(output.get("hand_pose_params")),
            "scale_params": self._to_python(output.get("scale_params")),
            "shape_params": self._to_python(output.get("shape_params")),
            "expr_params": self._to_python(output.get("expr_params")),
            "pred_joint_coords": self._to_python(output.get("pred_joint_coords")),
            "pred_global_rots": self._to_python(output.get("pred_global_rots")),
            "mhr_model_params": self._to_python(output.get("mhr_model_params")),
        }

    def _mesh_to_obj(self, vertices: Any, faces: np.ndarray | None) -> str:
        if faces is None:
            raise RuntimeError("SAM 3D Body faces not initialized")
        vertices_array = np.asarray(vertices, dtype=np.float32)
        faces_array = np.asarray(faces, dtype=np.int64)
        lines = ["# sam3d body mesh export"]
        lines.extend(f"v {x:.8f} {y:.8f} {z:.8f}" for x, y, z in vertices_array)
        lines.extend(
            f"f {int(a) + 1} {int(b) + 1} {int(c) + 1}"
            for a, b, c in faces_array
        )
        return "\n".join(lines) + "\n"

    def _build_mask_image(self, mask: Any, bbox: Any, width: int, height: int) -> Image.Image:
        if mask is not None:
            array = np.asarray(mask)
            array = np.squeeze(array)
            if array.ndim == 2:
                if array.dtype != np.uint8:
                    array = array.astype(np.float32)
                    scale = 255.0 if array.max() <= 1.0 else 1.0
                    array = np.clip(array * scale, 0, 255).astype(np.uint8)
                return Image.fromarray(array, mode="L")

        fallback = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(fallback)
        if bbox is not None:
            left, top, right, bottom = [float(item) for item in np.asarray(bbox).tolist()]
            draw.rectangle((left, top, right, bottom), fill=255)
        else:
            draw.rectangle((width * 0.30, height * 0.08, width * 0.70, height * 0.94), fill=255)
        return fallback

    def _build_masked_preview(self, image: Image.Image, mask_image: Image.Image) -> Image.Image:
        source = image.convert("RGBA")
        alpha = mask_image.resize(image.size)
        source.putalpha(alpha)
        background = Image.new("RGBA", image.size, (20, 24, 32, 255))
        background.alpha_composite(source)
        return background.convert("RGB")

    def _bbox_area_ratio(self, bbox: Any, width: int, height: int) -> float:
        if bbox is None:
            return 0.0
        left, top, right, bottom = [float(item) for item in np.asarray(bbox).tolist()]
        area = max(right - left, 0.0) * max(bottom - top, 0.0)
        total = max(width * height, 1)
        return area / float(total)

    def _mask_coverage_ratio(self, mask_image: Image.Image) -> float:
        mask_array = np.asarray(mask_image, dtype=np.float32)
        return float(mask_array.mean() / 255.0)

    def _reconstruction_score(
        self,
        validation: ValidationResult,
        output: dict[str, Any],
        mask_image: Image.Image,
        width: int,
        height: int,
    ) -> float:
        validation_score = {"pass": 0.92, "warning": 0.71, "reject": 0.2}[validation.decision]
        bbox_score = min(1.0, self._bbox_area_ratio(output.get("bbox"), width, height) * 2.2)
        mask_score = min(1.0, self._mask_coverage_ratio(mask_image) * 1.8)
        return (validation_score + bbox_score + mask_score) / 3.0

    def _resolve_device(self) -> str:
        requested = self.settings.device.strip().lower()
        if requested == "auto":
            return "cuda" if self._cuda_available() else "cpu"
        return requested

    def _has_local_checkpoint_source(self) -> bool:
        return bool(self.settings.checkpoint_path.strip() and self.settings.mhr_path.strip())

    def _required_core_modules(self) -> tuple[str, ...]:
        return (
            "braceexpand",
            "yacs",
            "einops",
            "hydra",
            "pyrootutils",
            "huggingface_hub",
        )

    def _module_available(self, module_name: str) -> bool:
        try:
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    def _cuda_available(self) -> bool:
        return bool(torch is not None and torch.cuda.is_available())

    def _normalize_component_name(self, value: str) -> str | None:
        normalized = value.strip().lower()
        if normalized in {"", "none", "off", "disabled", "false"}:
            return None
        return value.strip()

    def _to_python(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.floating, np.integer)):
            return value.item()
        if isinstance(value, dict):
            return {key: self._to_python(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._to_python(item) for item in value]
        return value
