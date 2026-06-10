from __future__ import annotations

from pipeline_common import PIPELINE, read_json, write_json


def main() -> int:
    metadata_path = PIPELINE / "garments" / "garment_metadata.json"
    if not metadata_path.exists():
        raise SystemExit("Run scripts/01_preprocess_assets.py first.")
    metadata = read_json(metadata_path)
    required = [
        "top_front_cutout",
        "top_back_cutout",
        "pants_front_cutout",
        "pants_back_cutout",
        "top_front_logo_mask",
        "top_back_logo_mask",
        "pants_back_pocket_mask",
    ]
    missing = [key for key in required if key not in metadata.get("outputs", {})]
    stage = {
        "status": "success" if not missing else "failed",
        "required_outputs": required,
        "missing": missing,
        "view_assignment": metadata.get("view_assignment", {}),
        "source_metadata": "assets/pipeline/garments/garment_metadata.json",
    }
    write_json(PIPELINE / "garments" / "stage4_garment_prep.json", stage)
    if missing:
        print("status=failed")
        print("missing=" + ",".join(missing))
        return 1
    print("status=success")
    print("stage4=assets/pipeline/garments/stage4_garment_prep.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
