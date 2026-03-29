from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from app.cli import main


class ReconstructionSmokeTest(unittest.TestCase):
    def test_providers_command_supports_sam3d_readiness(self) -> None:
        exit_code = main(["providers", "--provider", "sam3d"])
        self.assertEqual(exit_code, 0)

    def test_run_manifest_creates_expected_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            image_root = tmp_dir / "images"
            output_root = tmp_dir / "outputs"
            manifest_path = tmp_dir / "manifest.csv"

            for label in ("good", "warning", "reject"):
                (image_root / label).mkdir(parents=True, exist_ok=True)

            self._make_image(image_root / "good" / "sample_0001.jpg", color=(210, 180, 170))
            self._make_image(image_root / "warning" / "sample_0002.jpg", color=(115, 95, 85))
            self._make_image(image_root / "reject" / "sample_0003.jpg", size=(420, 540), color=(40, 40, 45))

            with manifest_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "sample_id",
                        "split_label",
                        "file_name",
                        "subject_count",
                        "body_visibility",
                        "occlusion_level",
                        "lighting_level",
                        "blur_level",
                        "background_complexity",
                        "perspective_level",
                        "clothing_looseness",
                        "pose_type",
                        "primary_reason",
                        "secondary_reasons",
                        "review_status",
                        "reviewer",
                        "dataset_version",
                        "notes",
                    ]
                )
                writer.writerow(["sample_0001", "good", "sample_0001.jpg", "single", "full", "none", "normal", "none", "simple", "normal", "normal", "front_neutral", "", "", "approved", "qa", "v0.1", ""])
                writer.writerow(["sample_0002", "warning", "sample_0002.jpg", "single", "full", "medium", "dark", "medium", "complex", "mild", "loose", "front_neutral", "LOOSE_CLOTHING", "COMPLEX_BACKGROUND", "approved", "qa", "v0.1", ""])
                writer.writerow(["sample_0003", "reject", "sample_0003.jpg", "single", "partial", "high", "very_dark", "high", "complex", "extreme", "very_loose", "other", "BODY_TRUNCATED", "LOW_RESOLUTION", "approved", "qa", "v0.1", ""])

            exit_code = main(
                [
                    "run-manifest",
                    "--manifest",
                    str(manifest_path),
                    "--image-root",
                    str(image_root),
                    "--output-root",
                    str(output_root),
                    "--provider",
                    "mock",
                    "--run-id",
                    "test_run",
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_root / "test_run" / "benchmark-summary.json").exists())
            self.assertTrue((output_root / "test_run" / "benchmark-run.csv").exists())
            self.assertTrue((output_root / "test_run" / "sample_0001").exists())
            self.assertTrue((output_root / "test_run" / "sample_0002").exists())
            self.assertTrue((output_root / "test_run" / "sample_0003").exists())

    @staticmethod
    def _make_image(path: Path, size: tuple[int, int] = (960, 1440), color: tuple[int, int, int] = (180, 170, 165)) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(image)
        width, height = size
        draw.ellipse((width * 0.40, height * 0.07, width * 0.60, height * 0.19), fill=(220, 198, 184))
        draw.rounded_rectangle((width * 0.34, height * 0.18, width * 0.66, height * 0.56), radius=28, fill=(80, 84, 112))
        draw.rectangle((width * 0.26, height * 0.20, width * 0.36, height * 0.52), fill=(96, 100, 130))
        draw.rectangle((width * 0.64, height * 0.20, width * 0.74, height * 0.52), fill=(96, 100, 130))
        draw.rectangle((width * 0.41, height * 0.56, width * 0.49, height * 0.94), fill=(42, 48, 70))
        draw.rectangle((width * 0.51, height * 0.56, width * 0.59, height * 0.94), fill=(42, 48, 70))
        draw.line((width * 0.18, height * 0.10, width * 0.82, height * 0.10), fill=(240, 240, 240), width=6)
        draw.line((width * 0.18, height * 0.84, width * 0.82, height * 0.84), fill=(28, 28, 28), width=8)
        image.save(path, quality=96)


if __name__ == "__main__":
    unittest.main()
