# Technical Pipeline

## Scope
This demo includes an executed SAM 3D Body technical pipeline for the fixed capstone sample. SAM 3D Body is used to produce the body mesh, measurements, and front/side/back guide maps. The final front/side/back viewer images are FASHN VTON outputs using a SAM Body-derived mannequin base; front/back are then mask-locked so the SAM body base is preserved outside the shirt and pants regions. User-created `guide/mannequin-*.png` reference images are not used in the final source chain.

## Executed Flow

1. Asset preprocessing
   - Script: `scripts/01_preprocess_assets.py`
   - Outputs:
     - `assets/pipeline/preprocessed/person_oriented.png`
     - `assets/pipeline/preprocessed/person_crop.png`
     - `assets/pipeline/garments/*_cutout.png`
     - `assets/pipeline/garments/*_mask.png`

2. Environment and model audit
   - Script: `scripts/00_env_audit.py`
   - Outputs:
     - `assets/pipeline/env/environment-report.json`
     - `assets/pipeline/env/model-access-report.json`
   - Result: `bys` conda environment sees CUDA through PyTorch on RTX 3090. `HF_TOKEN` presence is recorded without printing the value.

3. SAM 3D Body inference
   - Script: `scripts/02_run_sam3d_body.py`
   - Official repo: `external/sam-3d-body`
   - Outputs:
     - `assets/pipeline/sam3d/native_output.pt`
     - `assets/pipeline/sam3d/source_output_schema.json`
     - `assets/pipeline/sam3d/body_metadata.json`
     - `assets/pipeline/sam3d/sam3d_preview_front.png`
   - Evidence:
     - `body_metadata.json` has `status: success`
     - native output key used for mesh export: `0.pred_vertices`
     - face source: `assets/pipeline/sam3d/estimator_faces.npy`

4. Mesh export adapter
   - Script: `scripts/02b_export_sam3d_body_artifact.py`
   - Output:
     - `assets/pipeline/sam3d/body.ply`
   - Result:
     - 18,439 vertices
     - 36,874 faces

5. Guide rendering
   - Script: `scripts/03_render_guides.py`
   - Renderer: lightweight Python orthographic rasterizer
   - Outputs:
     - `assets/pipeline/guides/front_silhouette.png`
     - `assets/pipeline/guides/front_depth.png`
     - `assets/pipeline/guides/front_normal.png`
     - `assets/pipeline/guides/side_silhouette.png`
     - `assets/pipeline/guides/side_depth.png`
     - `assets/pipeline/guides/side_normal.png`
     - `assets/pipeline/guides/back_silhouette.png`
     - `assets/pipeline/guides/back_depth.png`
     - `assets/pipeline/guides/back_normal.png`
     - `assets/pipeline/guides/*_coarse_part_map.png`
   - Note: coarse part maps are not DensePose.

6. Guide-conditioned base fitting
   - Script: `scripts/05_generate_base_fitting.py`
   - Outputs:
     - `assets/pipeline/base_outputs/front_candidate_001.png`
     - `assets/pipeline/base_outputs/side_candidate_001.png`
     - `assets/pipeline/base_outputs/back_candidate_001.png`
     - `assets/pipeline/base_outputs/candidates.json`
   - These are rough deterministic candidates that explicitly consume the rendered SAM guide maps.

7. Deterministic draft generation and quality gate
   - Scripts:
     - `scripts/06_refine_outputs.py`
     - `scripts/07_select_final.py`
   - Outputs:
     - `assets/pipeline/refined_outputs/*_sam_body_base.png`
     - `assets/pipeline/refined_outputs/*_shirt_mask.png`
     - `assets/pipeline/refined_outputs/*_pants_mask.png`
     - `assets/pipeline/refined_outputs/refinement_manifest.json`
     - `assets/results/sam-mannequin-front.png`
     - `assets/results/sam-mannequin-side.png`
     - `assets/results/sam-mannequin-back.png`
   - Disclosure:
     - These deterministic SAM-guide composites are technical drafts only.
     - They failed visual QA for presentation quality and are not used as the final viewer output.
     - The failure is expected: silhouette masks alone do not create cloth thickness, believable sleeve geometry, or photorealistic fabric.

8. SAM Body-only mannequin base, VTON generation, and mask-locked finalization
   - Scripts:
     - `scripts/10_guard_viewer_contract.py`
     - `scripts/10_extract_sam_body_measurements.py`
     - `scripts/11_build_neutral_mannequin_guides.py`
     - `scripts/18_build_sam_body_only_mannequin_base.py`
     - `scripts/19_generate_sam_body_only_fashn_viewer.py`
     - `scripts/20_select_sam_body_only_viewer.py`
   - Outputs:
     - `assets/pipeline/viewer_hq/sam_measurements.json`
     - `assets/pipeline/viewer_hq/guides/neutral_guide_manifest.json`
     - `assets/pipeline/sam_body_only/base/sam_body_only_base_manifest.json`
     - `assets/pipeline/sam_body_only/fashn/sam_body_only_selection.json`
     - `assets/pipeline/sam_body_only/mask_locked/mask_locked_selection.json`
     - `assets/results/display/sam-body-only-front|side|back-contrast.png`
   - Result:
     - The selected side FASHN-generated viewer image is used as the side result.
     - The selected front/back FASHN-generated candidates are rebuilt through SAM body fixed shirt/pants lock masks, then written to `assets/results/sam-body-only-front|back.png` and the UI display paths.

## Presentation Claim
Use this wording:

> We ran SAM 3D Body on the fixed user image, exported the body mesh, extracted body measurements, and rendered front/side/back guide maps. We then built a SAM Body-derived mannequin base, generated clothed VTON candidates, and finalized front/back by locking the generated clothes to shirt/pants masks while preserving the SAM body outside those regions.

More precise technical wording:

> The 3-view viewer is a fixed-sample SAM Body-guided generation result. We actually run SAM 3D Body, export the mesh, extract measurements, and render front/side/back guide maps. The deterministic SAM-guide composites are rejected drafts. The final UI images are FASHN VTON results under `assets/results/sam-body-only-*.png`, with front/back mask-locked to the SAM body base.

Avoid this wording:

Do not describe the demo as a real-time, fully automatic, arbitrary-user commercial virtual try-on system.
Do not describe `guide/mannequin-*.png` as model output or as a final-generation input.

## Key Artifact Chain

```text
image/ fixed sample inputs
  -> assets/pipeline/preprocessed/
  -> assets/pipeline/sam3d/native_output.pt
  -> assets/pipeline/sam3d/body.ply
  -> assets/pipeline/guides/front|side|back_*.png
  -> assets/pipeline/base_outputs/*_candidate_001.png
  -> assets/pipeline/refined_outputs/*_refined_001.png
  -> assets/results/sam-mannequin-front|side|back.png  # quality-rejected technical drafts
  -> assets/pipeline/sam_body_only/base/*_sam_body_only_base.png
  -> assets/pipeline/sam_body_only/fashn/sam_body_only_selection.json
  -> assets/pipeline/sam_body_only/mask_locked/mask_locked_selection.json
  -> assets/results/sam-body-only-front|side|back.png
  -> assets/results/display/sam-body-only-front|side|back-contrast.png  # UI viewer result
```

## Verification
The paired verification plan is `.omx/plans/test-spec-technical-vton-pipeline.md`.
