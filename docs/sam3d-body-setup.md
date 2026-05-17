# SAM 3D Body Setup for `bys`

This project uses the existing `bys` conda environment for the SAM 3D Body
spike.

## Current Local Status

- GPU is visible when commands run outside the sandbox.
- GPU: NVIDIA GeForce RTX 3090, 24576 MiB.
- `bys` Python: 3.10.19.
- `bys` PyTorch: 2.10.0+cu128.
- SAM 3D Body repo exists at `external/sam-3d-body`.
- MoGe is installed in `bys`.
- `sam_3d_body`, `moge`, and `detectron2` import successfully in `bys`.
- Sample image exists at `assets/sample-inputs/body/dancing.jpg`.
- Hugging Face auth works with the token from `.env`.
- `model.ckpt` and `assets/mhr_model.pt` are downloaded.
- `scripts/model_spike.py --run-sam --strict` passes.
- SAM output has been exported to the project body contract at
  `results/sam3d-body/dancing/body/`.

Remaining note:
- Commands that need GPU or network access must run outside the sandbox.

## Fix Hugging Face Auth

Request and accept access for:

```text
facebook/sam-3d-body-dinov3
```

Then refresh local auth:

```bash
conda run -n bys hf auth login
```

Verify:

```bash
conda run -n bys hf auth whoami
```

## Download Checkpoints

If checkpoints need to be refreshed:

```bash
conda run -n bys hf download facebook/sam-3d-body-dinov3 \
  --local-dir checkpoints/sam-3d-body-dinov3
```

Expected files:

```text
checkpoints/sam-3d-body-dinov3/model.ckpt
checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt
```

## Re-run Phase 0 Gate

```bash
conda run -n bys python scripts/model_spike.py --run-sam --strict
```

## Export Project Body Contract

After the strict gate passes:

```bash
conda run -n bys python scripts/run_sam3d_body_contract.py \
  --image assets/sample-inputs/body/dancing.jpg \
  --output-dir results/sam3d-body/dancing/body
```

Expected output:

```text
results/sam3d-body/dancing/body/body.glb
results/sam3d-body/dancing/body/landmarks.json
results/sam3d-body/dancing/body/body_metadata.json
```
