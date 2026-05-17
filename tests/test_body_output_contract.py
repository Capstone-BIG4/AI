import tempfile
import unittest
from pathlib import Path

from backend.app.contracts.body_output import (
    BodyOutputContractError,
    validate_body_output,
)
from backend.app.pipelines.fallback_body import create_fallback_body_output
from backend.app.pipelines.sam3d_body_contract import build_landmarks


class BodyOutputContractTests(unittest.TestCase):
    def test_fallback_output_satisfies_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "body"

            result = create_fallback_body_output(output_dir, job_id="test-job")

            self.assertEqual(result["metadata"]["job_id"], "test-job")
            self.assertEqual((output_dir / "body.glb").read_bytes()[:4], b"glTF")
            self.assertTrue((output_dir / "landmarks.json").is_file())
            self.assertTrue((output_dir / "body_metadata.json").is_file())

    def test_missing_file_fails_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "body"
            create_fallback_body_output(output_dir, job_id="test-job")
            (output_dir / "body.glb").unlink()

            with self.assertRaises(BodyOutputContractError):
                validate_body_output(output_dir)

    def test_sam_landmark_builder_outputs_contract_keys(self) -> None:
        keypoints = [[float(idx), float(idx + 1), float(idx + 2)] for idx in range(70)]

        landmarks = build_landmarks(keypoints)

        self.assertEqual(landmarks["coordinate_system"], "viewer")
        self.assertIn("neck", landmarks["points"])
        self.assertIn("left_shoulder", landmarks["points"])
        self.assertIn("right_ankle", landmarks["points"])
        self.assertIn("shoulder_width", landmarks["measurements_estimated"])


if __name__ == "__main__":
    unittest.main()
