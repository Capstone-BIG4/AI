# AI Pipeline

The AI layer lives in the root `scripts/` directory so every stage can resolve repository-relative assets consistently.

Primary stages:

1. `01_preprocess_assets.py`
2. `02_run_sam3d_body.py`
3. `03_render_guides.py`
4. `18_build_sam_body_only_mannequin_base.py`
5. `19_generate_sam_body_only_fashn_viewer.py`
6. `20_select_sam_body_only_viewer.py`
7. `10_guard_viewer_contract.py`

Read the detailed explanation in `docs/technical-pipeline.md`.
