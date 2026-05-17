import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from backend.app.contracts.garment_template import validate_garment_template
from backend.app.contracts.garment_texture import validate_garment_textures
from backend.app.pipelines.garment_templates import build_template_assets
from backend.app.pipelines.garment_textures import (
    GarmentImageInputs,
    generate_garment_textures,
)
from backend.app.pipelines.fallback_body import create_fallback_body_output
from backend.app.pipelines.canonical_body import create_canonical_body_output
from backend.app.pipelines.hybrid_fitting import build_landmark_fitted_garments
from backend.app.pipelines.upright_body import create_upright_body_output


class GarmentAssetTests(unittest.TestCase):
    def test_garment_texture_generation_satisfies_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cloth_dir = root / "cloth"
            cloth_dir.mkdir()
            self._write_sample_png(cloth_dir / "front.png", (220, 80, 80, 255))
            self._write_sample_png(cloth_dir / "back.png", (180, 60, 60, 255))
            self._write_sample_png(cloth_dir / "front_pants.png", (40, 90, 150, 255))
            self._write_sample_png(cloth_dir / "back_pants.png", (30, 70, 125, 255))

            output_dir = root / "garments"
            result = generate_garment_textures(
                GarmentImageInputs(
                    top_front=cloth_dir / "front.png",
                    top_back=cloth_dir / "back.png",
                    pants_front=cloth_dir / "front_pants.png",
                    pants_back=cloth_dir / "back_pants.png",
                ),
                output_dir,
                texture_size=256,
            )

            self.assertEqual(result["root"], str(output_dir))
            self.assertFalse(result["quality"]["top"]["back_estimated"])
            self.assertGreater(result["quality"]["top"]["front_mask_confidence"], 0.7)
            validate_garment_textures(output_dir)

    def test_garment_templates_satisfy_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            tshirt = build_template_assets("tshirt", root / "tshirt", texture_uri=None)
            pants = build_template_assets("pants", root / "pants", texture_uri=None)

            self.assertEqual(tshirt["category"], "tshirt")
            self.assertEqual(pants["category"], "pants")
            self.assertIn("left_shoulder", tshirt["metadata"]["anchors"])
            self.assertIn("waist_center", pants["metadata"]["anchors"])
            validate_garment_template(root / "tshirt", category="tshirt")
            validate_garment_template(root / "pants", category="pants")

    def test_hybrid_fitting_uses_landmark_anchor_method(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            body_dir = root / "body"
            create_fallback_body_output(body_dir, job_id="fit-test")
            upright_body_dir = root / "upright-body"
            upright_body = create_upright_body_output(body_dir, upright_body_dir)
            canonical_body_dir = root / "canonical-body"
            canonical_body = create_canonical_body_output(body_dir, canonical_body_dir)
            tshirt_dir = root / "templates" / "tshirt"
            pants_dir = root / "templates" / "pants"
            build_template_assets("tshirt", tshirt_dir, texture_uri=None)
            build_template_assets("pants", pants_dir, texture_uri=None)
            top_atlas = root / "top_texture_atlas.png"
            pants_atlas = root / "pants_texture_atlas.png"
            self._write_atlas(top_atlas, (210, 70, 70, 255))
            self._write_atlas(pants_atlas, (40, 80, 150, 255))

            report = build_landmark_fitted_garments(
                body_dir=upright_body_dir,
                scene_dir=root / "scene",
                top_atlas=top_atlas,
                pants_atlas=pants_atlas,
                tshirt_template_dir=tshirt_dir,
                pants_template_dir=pants_dir,
            )

            self.assertEqual(upright_body["metadata"]["model_name"], "sam-3d-body-upright-viewer")
            self.assertEqual(canonical_body["metadata"]["model_name"], "canonical-body-from-sam-proportions")
            self.assertEqual(report["method"], "landmark_anchor_hybrid_v1")
            self.assertIn("body.left_shoulder", report["top"]["anchors_used"])
            self.assertIn("body.waist_center", report["pants"]["anchors_used"])
            self.assertEqual(report["top"]["fit_checks"]["status"], "pass")
            self.assertEqual(report["pants"]["fit_checks"]["status"], "pass")
            self.assertEqual(report["top"]["fit_checks"]["penetration_vertex_count"], 0)
            self.assertEqual(report["pants"]["fit_checks"]["penetration_vertex_count"], 0)
            self.assertEqual((root / "scene" / "top.glb").read_bytes()[:4], b"glTF")
            self.assertEqual((root / "scene" / "pants.glb").read_bytes()[:4], b"glTF")

    def _write_sample_png(self, path: Path, color: tuple[int, int, int, int]) -> None:
        image = Image.new("RGBA", (180, 240), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((45, 35, 135, 210), radius=8, fill=color)
        image.save(path)

    def _write_atlas(self, path: Path, color: tuple[int, int, int, int]) -> None:
        image = Image.new("RGBA", (256, 256), color)
        image.save(path)


if __name__ == "__main__":
    unittest.main()
