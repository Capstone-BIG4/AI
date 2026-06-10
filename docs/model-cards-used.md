# Model Notes

This document records the model responsibilities used by the demo pipeline.

## SAM 3D Body

- Role: body mesh and body measurement estimation from one user photo.
- Output used by this repo: body preview, guide maps, and body proportion information.
- Why it is used: it provides a geometry-aware body anchor before garment generation.

## VTON Generator

- Role: generate shirt and pants fitting candidates from front/back garment references.
- Output used by this repo: front, side, and back mannequin outfit candidates.
- Why it is used: direct garment generation produces more natural fabric texture than drawing flat color regions onto a silhouette.

## Mask-Locked Finalization

- Role: preserve SAM body regions while applying garment pixels only inside shirt and pants masks.
- Output used by this repo: final viewer images and proof masks.
- Why it is used: it reduces body drift, neck/head artifacts, and boundary mismatch in front/back views.

## UI and API Layer

- Role: make the pipeline explainable through upload slots, run state, result preview, and the 2.5D viewer.
- Output used by this repo: `tryon-2d.png` and the front/side/back viewer paths returned by `/api/results`.

## Limitation Statement

The current system demonstrates a controlled high-quality sample and an implementation-ready pipeline. Generalization to arbitrary users and garments requires broader testing, more automated scoring, and additional model evaluation.
