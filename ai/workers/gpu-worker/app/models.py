from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ValidationDecision = Literal["pass", "warning", "reject"]
FinalStatus = Literal["body_ready", "needs_reupload", "failed"]


class ManifestSample(BaseModel):
    sample_id: str
    split_label: str | None = None
    file_name: str
    subject_count: str = "single"
    body_visibility: str = "full"
    occlusion_level: str = "none"
    lighting_level: str = "normal"
    blur_level: str = "none"
    background_complexity: str = "simple"
    perspective_level: str = "normal"
    clothing_looseness: str = "normal"
    pose_type: str = "front_neutral"
    primary_reason: str | None = None
    secondary_reasons: str | None = None
    review_status: str | None = None
    reviewer: str | None = None
    dataset_version: str | None = None
    notes: str | None = None

    @property
    def secondary_reason_list(self) -> list[str]:
        if not self.secondary_reasons:
            return []
        return [item.strip() for item in self.secondary_reasons.split("|") if item.strip()]


class ValidationMetrics(BaseModel):
    width: int
    height: int
    aspect_ratio: float
    brightness_mean: float
    blur_score: float
    portrait_bias: float
    file_size_bytes: int


class ValidationResult(BaseModel):
    decision: ValidationDecision
    reasons: list[str] = Field(default_factory=list)
    warning_flags: list[str] = Field(default_factory=list)
    metrics: ValidationMetrics
    expected_label: str | None = None


class EnvironmentSnapshot(BaseModel):
    python_version: str
    executable: str
    platform: str
    provider: str
    provider_version: str
    torch_version: str | None = None
    cuda_available: bool = False
    cuda_device_count: int = 0
    cuda_device_name: str | None = None


class ArtifactKeys(BaseModel):
    raw_image: str
    normalized_image: str | None = None
    crop_preview: str | None = None
    person_mask: str | None = None
    masked_preview: str | None = None
    keypoints_json: str | None = None
    body_params_json: str | None = None
    raw_mesh_obj: str | None = None
    validation_json: str
    timings_json: str
    environment_json: str
    process_log: str
    summary_json: str


class SampleRunResult(BaseModel):
    run_id: str
    sample_id: str
    job_id: str
    provider: str
    provider_version: str
    final_status: FinalStatus
    validation_result: ValidationDecision
    reconstruction_result: str
    expected_label: str | None = None
    error_code: str | None = None
    notes: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int]
    peak_vram_mb: int = 0
    quality_scores: dict[str, float] = Field(default_factory=dict)
    artifact_keys: ArtifactKeys
    validation: ValidationResult
    environment: EnvironmentSnapshot


class BenchmarkSummary(BaseModel):
    run_id: str
    provider: str
    provider_version: str
    total_samples: int
    validation_pass_rate: float
    validation_reject_rate: float
    reconstruction_success_rate: float
    average_total_latency_ms: float
    average_peak_vram_mb: float
    failure_breakdown: dict[str, int] = Field(default_factory=dict)
    split_breakdown: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sample_results: list[SampleRunResult] = Field(default_factory=list)
