from __future__ import annotations

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config import ReconstructionSettings
from app.models import (
    ArtifactKeys,
    BenchmarkSummary,
    EnvironmentSnapshot,
    ManifestSample,
    SampleRunResult,
)
from app.providers import BaseReconstructionProvider
from app.utils.files import copy_file, ensure_dir, write_csv, write_json, write_text
from app.utils.images import center_crop_preview, load_image, resize_to_max_side, validate_image

try:
    import torch
except Exception:  # pragma: no cover - optional dependency path
    torch = None


SUMMARY_FIELDNAMES = [
    "run_id",
    "sample_id",
    "split_label",
    "validation_result",
    "reconstruction_result",
    "final_status",
    "latency_ms",
    "validation_ms",
    "reconstruction_ms",
    "export_ms",
    "peak_vram_mb",
    "segmentation_score",
    "pose_confidence",
    "reconstruction_score",
    "measurement_reliability",
    "error_code",
    "notes",
]


class ReconstructionPipeline:
    def __init__(self, settings: ReconstructionSettings, provider: BaseReconstructionProvider) -> None:
        self.settings = settings
        self.provider = provider

    def run_single(
        self,
        input_path: Path,
        output_root: Path,
        sample: ManifestSample | None = None,
        run_id: str | None = None,
    ) -> SampleRunResult:
        timestamp = datetime.now(timezone.utc)
        run_id = run_id or f"recon_{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
        sample_id = sample.sample_id if sample else input_path.stem
        job_id = f"job_local_{sample_id}_{timestamp.strftime('%Y%m%d%H%M%S')}"
        sample_root = output_root / run_id / sample_id
        log_lines = [
            f"[{timestamp.isoformat()}] run_id={run_id}",
            f"[{timestamp.isoformat()}] sample_id={sample_id}",
            f"[{timestamp.isoformat()}] provider={self.provider.name}:{self.provider.version}",
        ]

        raw_key = sample_root / timestamp.strftime("raw-images/%Y/%m/%d") / job_id / f"original{input_path.suffix.lower()}"
        normalized_key = sample_root / "preprocessed" / job_id / "normalized.png"
        crop_key = sample_root / "preprocessed" / job_id / "crop_preview.jpg"
        mask_key = sample_root / "masks" / job_id / "person_mask.png"
        masked_preview_key = sample_root / "masks" / job_id / "masked_preview.jpg"
        keypoints_key = sample_root / "poses" / job_id / "keypoints.json"
        reconstruction_root = sample_root / "reconstruction" / job_id
        body_params_key = reconstruction_root / "body_params.json"
        raw_mesh_key = reconstruction_root / "raw_mesh.obj"
        reports_root = sample_root / "reports" / job_id
        validation_key = reports_root / "validation.json"
        timings_key = reports_root / "timings.json"
        environment_key = reports_root / "environment.json"
        summary_key = reports_root / "summary.json"
        process_log_key = reports_root / "process.log"

        copy_file(input_path, raw_key)
        log_lines.append(f"raw_image={raw_key.relative_to(sample_root)}")

        load_started = perf_counter()
        loaded = load_image(input_path)
        image = loaded.image
        validation = validate_image(
            image=image,
            file_size_bytes=loaded.file_size_bytes,
            settings=self.settings,
            manifest_sample=sample,
        )
        validation_ms = self._elapsed_ms(load_started)
        log_lines.append(f"validation_decision={validation.decision}")
        if validation.warning_flags:
            log_lines.append(f"validation_warnings={','.join(validation.warning_flags)}")
        if validation.reasons:
            log_lines.append(f"validation_reasons={','.join(validation.reasons)}")

        environment = self._environment_snapshot()
        write_json(validation_key, validation.model_dump(mode="json"))
        write_json(environment_key, environment.model_dump(mode="json"))

        if validation.decision == "reject":
            timings_ms = {
                "validation_ms": validation_ms,
                "reconstruction_ms": 0,
                "export_ms": 0,
                "total_ms": validation_ms,
            }
            write_json(timings_key, timings_ms)
            write_text(process_log_key, "\n".join(log_lines) + "\n")
            result = SampleRunResult(
                run_id=run_id,
                sample_id=sample_id,
                job_id=job_id,
                provider=self.provider.name,
                provider_version=self.provider.version,
                final_status="needs_reupload",
                validation_result="reject",
                reconstruction_result="skipped",
                expected_label=sample.split_label if sample else None,
                error_code="INPUT_REJECTED",
                notes=["validation rejected input before reconstruction"],
                timings_ms=timings_ms,
                peak_vram_mb=self._peak_vram_mb(),
                quality_scores={},
                artifact_keys=self._artifact_keys(
                    sample_root=sample_root,
                    raw_key=raw_key,
                    normalized_key=None,
                    crop_key=None,
                    mask_key=None,
                    masked_preview_key=None,
                    keypoints_key=None,
                    body_params_key=None,
                    raw_mesh_key=None,
                    validation_key=validation_key,
                    timings_key=timings_key,
                    environment_key=environment_key,
                    process_log_key=process_log_key,
                    summary_key=summary_key,
                ),
                validation=validation,
                environment=environment,
            )
            write_json(summary_key, result.model_dump(mode="json"))
            return result

        reconstruct_started = perf_counter()
        normalized = resize_to_max_side(image=image, max_side=self.settings.max_side)
        ensure_dir(normalized_key.parent)
        normalized.save(normalized_key)
        crop_preview = center_crop_preview(normalized, self.settings.crop_ratio)
        crop_preview.save(crop_key, quality=92)

        provider_output = self.provider.run(image=normalized, sample_id=sample_id, validation=validation)
        ensure_dir(mask_key.parent)
        ensure_dir(reconstruction_root)
        provider_output.mask_image.save(mask_key)
        provider_output.masked_preview_image.save(masked_preview_key, quality=92)
        write_json(keypoints_key, {"sample_id": sample_id, "keypoints": provider_output.keypoints})
        write_json(body_params_key, provider_output.body_params)
        write_text(raw_mesh_key, provider_output.raw_mesh_obj)
        reconstruction_ms = self._elapsed_ms(reconstruct_started)

        export_started = perf_counter()
        log_lines.append(f"raw_mesh={raw_mesh_key.relative_to(sample_root)}")
        log_lines.append(f"keypoints={keypoints_key.relative_to(sample_root)}")
        log_lines.append(f"body_params={body_params_key.relative_to(sample_root)}")
        export_ms = self._elapsed_ms(export_started)
        timings_ms = {
            "validation_ms": validation_ms,
            "reconstruction_ms": reconstruction_ms,
            "export_ms": export_ms,
            "total_ms": validation_ms + reconstruction_ms + export_ms,
        }
        write_json(timings_key, timings_ms)
        write_text(process_log_key, "\n".join(log_lines) + "\n")

        result = SampleRunResult(
            run_id=run_id,
            sample_id=sample_id,
            job_id=job_id,
            provider=self.provider.name,
            provider_version=self.provider.version,
            final_status="body_ready",
            validation_result=validation.decision,
            reconstruction_result="success",
            expected_label=sample.split_label if sample else None,
            notes=provider_output.notes,
            timings_ms=timings_ms,
            peak_vram_mb=self._peak_vram_mb(),
            quality_scores=dict(provider_output.quality_scores),
            artifact_keys=self._artifact_keys(
                sample_root=sample_root,
                raw_key=raw_key,
                normalized_key=normalized_key,
                crop_key=crop_key,
                mask_key=mask_key,
                masked_preview_key=masked_preview_key,
                keypoints_key=keypoints_key,
                body_params_key=body_params_key,
                raw_mesh_key=raw_mesh_key,
                validation_key=validation_key,
                timings_key=timings_key,
                environment_key=environment_key,
                process_log_key=process_log_key,
                summary_key=summary_key,
            ),
            validation=validation,
            environment=environment,
        )
        write_json(summary_key, result.model_dump(mode="json"))
        return result

    def run_manifest(
        self,
        manifest_path: Path,
        image_root: Path,
        output_root: Path,
        run_id: str | None = None,
    ) -> BenchmarkSummary:
        from app.utils.files import read_manifest

        run_id = run_id or f"recon_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        samples = read_manifest(manifest_path)
        results: list[SampleRunResult] = []

        for sample in samples:
            image_path = self._resolve_image_path(image_root=image_root, sample=sample)
            results.append(self.run_single(input_path=image_path, output_root=output_root, sample=sample, run_id=run_id))

        summary = self._build_summary(run_id=run_id, results=results)
        summary_root = output_root / run_id
        write_json(summary_root / "benchmark-summary.json", summary.model_dump(mode="json"))
        write_csv(summary_root / "benchmark-run.csv", SUMMARY_FIELDNAMES, [self._to_summary_row(item) for item in results])
        return summary

    def _resolve_image_path(self, image_root: Path, sample: ManifestSample) -> Path:
        candidates = [
            image_root / sample.file_name,
            image_root / sample.split_label / sample.file_name if sample.split_label else None,
            image_root / "images" / sample.split_label / sample.file_name if sample.split_label else None,
        ]
        for candidate in candidates:
            if candidate is not None and candidate.exists():
                return candidate
        raise FileNotFoundError(f"sample image not found for {sample.sample_id}: {sample.file_name}")

    def _build_summary(self, run_id: str, results: list[SampleRunResult]) -> BenchmarkSummary:
        total = len(results)
        if total == 0:
            return BenchmarkSummary(
                run_id=run_id,
                provider=self.provider.name,
                provider_version=self.provider.version,
                total_samples=0,
                validation_pass_rate=0.0,
                validation_reject_rate=0.0,
                reconstruction_success_rate=0.0,
                average_total_latency_ms=0.0,
                average_peak_vram_mb=0.0,
                sample_results=[],
            )

        pass_count = sum(1 for item in results if item.validation_result != "reject")
        reject_count = sum(1 for item in results if item.validation_result == "reject")
        success_count = sum(1 for item in results if item.reconstruction_result == "success")
        failure_breakdown: dict[str, int] = {}
        split_breakdown: dict[str, dict[str, Any]] = {}

        for item in results:
            if item.error_code:
                failure_breakdown[item.error_code] = failure_breakdown.get(item.error_code, 0) + 1
            split_key = item.expected_label or "unlabeled"
            split_stats = split_breakdown.setdefault(
                split_key,
                {"count": 0, "success": 0, "reject": 0, "avg_latency_ms": 0.0},
            )
            split_stats["count"] += 1
            split_stats["success"] += 1 if item.reconstruction_result == "success" else 0
            split_stats["reject"] += 1 if item.validation_result == "reject" else 0

        for split_key, split_stats in split_breakdown.items():
            split_items = [item for item in results if (item.expected_label or "unlabeled") == split_key]
            split_stats["avg_latency_ms"] = round(
                statistics.mean(item.timings_ms["total_ms"] for item in split_items),
                2,
            )

        return BenchmarkSummary(
            run_id=run_id,
            provider=self.provider.name,
            provider_version=self.provider.version,
            total_samples=total,
            validation_pass_rate=round(pass_count / total, 4),
            validation_reject_rate=round(reject_count / total, 4),
            reconstruction_success_rate=round(success_count / total, 4),
            average_total_latency_ms=round(statistics.mean(item.timings_ms["total_ms"] for item in results), 2),
            average_peak_vram_mb=round(statistics.mean(item.peak_vram_mb for item in results), 2),
            failure_breakdown=failure_breakdown,
            split_breakdown=split_breakdown,
            sample_results=results,
        )

    def _artifact_keys(
        self,
        *,
        sample_root: Path,
        raw_key: Path,
        normalized_key: Path | None,
        crop_key: Path | None,
        mask_key: Path | None,
        masked_preview_key: Path | None,
        keypoints_key: Path | None,
        body_params_key: Path | None,
        raw_mesh_key: Path | None,
        validation_key: Path,
        timings_key: Path,
        environment_key: Path,
        process_log_key: Path,
        summary_key: Path,
    ) -> ArtifactKeys:
        rel = lambda path: str(path.relative_to(sample_root)) if path is not None else None
        return ArtifactKeys(
            raw_image=rel(raw_key) or "",
            normalized_image=rel(normalized_key),
            crop_preview=rel(crop_key),
            person_mask=rel(mask_key),
            masked_preview=rel(masked_preview_key),
            keypoints_json=rel(keypoints_key),
            body_params_json=rel(body_params_key),
            raw_mesh_obj=rel(raw_mesh_key),
            validation_json=rel(validation_key) or "",
            timings_json=rel(timings_key) or "",
            environment_json=rel(environment_key) or "",
            process_log=rel(process_log_key) or "",
            summary_json=rel(summary_key) or "",
        )

    def _environment_snapshot(self) -> EnvironmentSnapshot:
        snapshot = EnvironmentSnapshot(
            python_version=sys.version.split()[0],
            executable=sys.executable,
            platform=sys.platform,
            provider=self.provider.name,
            provider_version=self.provider.version,
        )
        if torch is None:
            return snapshot

        snapshot.torch_version = getattr(torch, "__version__", None)
        snapshot.cuda_available = bool(torch.cuda.is_available())
        snapshot.cuda_device_count = int(torch.cuda.device_count())
        if snapshot.cuda_available and snapshot.cuda_device_count > 0:
            snapshot.cuda_device_name = torch.cuda.get_device_name(0)
        return snapshot

    def _peak_vram_mb(self) -> int:
        if torch is None or not torch.cuda.is_available():
            return 0
        try:
            return int(torch.cuda.max_memory_allocated() / (1024 * 1024))
        except Exception:
            return 0

    def _to_summary_row(self, item: SampleRunResult) -> dict[str, Any]:
        return {
            "run_id": item.run_id,
            "sample_id": item.sample_id,
            "split_label": item.expected_label or "",
            "validation_result": item.validation_result,
            "reconstruction_result": item.reconstruction_result,
            "final_status": item.final_status,
            "latency_ms": item.timings_ms["total_ms"],
            "validation_ms": item.timings_ms["validation_ms"],
            "reconstruction_ms": item.timings_ms["reconstruction_ms"],
            "export_ms": item.timings_ms["export_ms"],
            "peak_vram_mb": item.peak_vram_mb,
            "segmentation_score": item.quality_scores.get("validation_score", 0),
            "pose_confidence": item.quality_scores.get("validation_score", 0),
            "reconstruction_score": item.quality_scores.get("reconstruction_score", 0),
            "measurement_reliability": item.quality_scores.get("reconstruction_score", 0),
            "error_code": item.error_code or "",
            "notes": " | ".join(item.notes),
        }

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int(round((perf_counter() - start) * 1000))
