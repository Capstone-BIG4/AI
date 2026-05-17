# SAM-Neutral 3D Outfit Preview Prototype

Standalone prototype for a body-based virtual fitting preview. It takes a
single-person full-body photo, exports a SAM 3D Body contract, derives a
neutral SAM/MHR mannequin from the same predicted shape/scale, and fits one
short-sleeve top plus one long pants sample for a Three.js 360 viewer.

Generated body meshes, SAM params, checkpoints, `.env`, and personal body photos
are intentionally not committed. Recreate them locally with the commands below.

## Phase 0 Commands

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run the static viewer:

```bash
npm install
npm run dev:viewer
```

Open:

```text
http://127.0.0.1:4173/frontend/
```

Verify the viewer:

```bash
python scripts/verify_viewer.py
```

## SAM Body Export

Expected local paths:

```text
external/sam-3d-body/
checkpoints/sam-3d-body-dinov3/model.ckpt
checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt
assets/sample-inputs/body/<your-full-body-photo>
```

Export both the source-pose SAM body and the neutral mannequin:

```bash
conda run -n bys env MPLCONFIGDIR=/tmp/matplotlib \
  python scripts/run_sam3d_body_contract.py \
  --image assets/sample-inputs/body/<your-full-body-photo> \
  --output-dir results/sam3d-body/byun/body \
  --neutral-output-dir results/neutral-body/byun/body \
  --job-id byun-sam3d-body \
  --neutral-job-id byun-neutral-sam3d-body
```

Then generate garment textures, templates, and the fitted scene from
`assets/sample-inputs/cloth/`:

```bash
conda run -n bys python scripts/generate_garment_assets.py \
  --fit-body-mode neutral \
  --body-dir results/sam3d-body/byun/body \
  --neutral-body-dir results/neutral-body/byun/body
```

This writes:

```text
results/garments/sample/
assets/templates/tshirt/
assets/templates/pants/
results/neutral-body/byun/body/
results/fitted/byun/scene/
```

## Notes

- The neutral mannequin is generated from SAM/MHR shape and scale params with
  zeroed pose, then normalized to viewer Y-up and front-facing coordinates.
- `sam_params.json` is generated locally and ignored by git because it is derived
  from the user body photo.
- The current garment mesh is a prototype shell. It checks collision clearance
  but is not yet a production cloth simulation.
