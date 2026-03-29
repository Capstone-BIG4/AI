#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${CONDA_DEFAULT_ENV:-}" ]]; then
  echo "conda environment 비활성 상태"
  echo "권장: conda activate bys"
fi

python -m pip install \
  pytorch-lightning \
  pyrender \
  opencv-python \
  yacs \
  scikit-image \
  einops \
  timm \
  dill \
  pandas \
  rich \
  hydra-core \
  hydra-submitit-launcher \
  hydra-colorlog \
  pyrootutils \
  webdataset \
  chump \
  networkx==3.2.1 \
  roma \
  joblib \
  seaborn \
  wandb \
  appdirs \
  ffmpeg \
  cython \
  jsonlines \
  pytest \
  xtcocotools \
  loguru \
  optree \
  fvcore \
  black \
  pycocotools \
  tensorboard \
  huggingface_hub \
  braceexpand

python -m pip install \
  'git+https://github.com/facebookresearch/detectron2.git@a1ce2f9' \
  --no-build-isolation \
  --no-deps

echo "공식 INSTALL.md 기준 core dependency 설치 경로"
echo "optional:"
echo "  MoGe2: python -m pip install git+https://github.com/microsoft/MoGe.git"
echo "  SAM3 : git clone https://github.com/facebookresearch/sam3.git && cd sam3 && python -m pip install -e . && python -m pip install decord psutil"
