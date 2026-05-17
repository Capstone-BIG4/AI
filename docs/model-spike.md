# Phase 0 Model Spike Report

Generated at: `2026-05-17T04:59:42.138897+00:00`

## Purpose

This report checks whether the local environment is ready to run SAM 3D Body and
whether the project can already produce the phase-0 body output contract:

```text
body.glb
landmarks.json
body_metadata.json
```

## Paths

- SAM 3D Body repo: `/home/bys0626/capstone/external/sam-3d-body`
- Checkpoint path: `/home/bys0626/capstone/checkpoints/sam-3d-body-dinov3/model.ckpt`
- MHR model path: `/home/bys0626/capstone/checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt`
- Sample image dir: `/home/bys0626/capstone/assets/sample-inputs/body`
- Output root: `/home/bys0626/capstone/results/spike`

## Environment Checks

| Check | Status | Detail |
| --- | --- | --- |
| `python` | ok | 3.10.19 (main, Oct 21 2025, 16:43:05) [GCC 11.2.0] |
| `python_expected` | warn | Current Python is 3.10; upstream install guide uses Python 3.11. |
| `torch` | ok | Python module 'torch' is importable. |
| `torch_cuda` | ok | torch 2.10.0+cu128, CUDA 12.8, devices: ['NVIDIA GeForce RTX 3090'] |
| `nvidia_smi` | ok | NVIDIA GeForce RTX 3090, 24576 MiB, 535.288.01 |
| `hf_auth` | ok | Hugging Face auth active for user:  dbstjd. |
| `sam_repo` | ok | Found SAM 3D Body repo at /home/bys0626/capstone/external/sam-3d-body |
| `sam_python_import` | ok | sam_3d_body imports from local repo. |
| `checkpoint` | ok | Found /home/bys0626/capstone/checkpoints/sam-3d-body-dinov3/model.ckpt |
| `mhr_model` | ok | Found /home/bys0626/capstone/checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt |
| `sample_images` | ok | Found 1 sample image(s) under /home/bys0626/capstone/assets/sample-inputs/body |

## Fallback Body Contract

Status: `ok`

Output directory:

```text
/home/bys0626/capstone/results/spike/phase0-fallback/body
```

Generated files:

- `body.glb`
- `landmarks.json`
- `body_metadata.json`

This is a development fallback only. It must not be presented as SAM 3D Body
reconstruction output.


## Real SAM 3D Body Demo Run

Status: `ok`

demo.py completed in 85.7s; log: /home/bys0626/capstone/results/spike/phase0-fallback/sam-raw/demo-command.log


## Current Verdict

- Real SAM 3D Body prerequisites are present.
- Fallback body output contract generation is working.
- Real SAM 3D Body demo execution is working.

## Next Actions

1. Export the project body contract:

```bash
conda run -n bys python scripts/run_sam3d_body_contract.py \
  --image assets/sample-inputs/body/dancing.jpg \
  --output-dir results/sam3d-body/dancing/body
```
2. Continue with the Milestone 1 viewer and garment template work.
