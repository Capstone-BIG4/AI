# Code Review Notes

## Review Scope

The public repo was reviewed for the capstone AI demo handoff. The review focused on correctness, repo hygiene, public documentation, secret safety, and whether the implementation matches the current SAM-guided front/side/back target.

## Findings and Resolutions

1. Stale project direction

   The previous repository structure described a GLB/Blender cloth-simulation direction. That conflicted with the current 2.5D SAM-guided VTON output. The stale docs and folders were replaced with the current frontend, backend, scripts, assets, and documentation.

2. Local experiment leakage risk

   Older experiments contained absolute local paths and unrelated model trials. Those files were not copied into the public repo. The public script set now contains only the supported pipeline stages and verification scripts.

3. Secret handling

   `.env` is ignored and only `.env.example` is committed. The token leak checker scans public text artifacts and exits successfully when no local token is present.

4. Public artifact clarity

   The repo now separates UI code, API code, AI scripts, selected assets, and documentation. `assets/manifest.json` provides a small explicit result contract instead of a large mixed experiment manifest.

5. License

   The repository uses the MIT license.

## Remaining Risks

- GPU generation depends on local model setup and credentials.
- VTON quality can vary by pose, garment, and lighting.
- Full arbitrary-user robustness is a future evaluation task.
- The side view is stronger than the hardest front/back boundary cases, so mask-locked finalization remains important.
