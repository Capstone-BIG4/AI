# AI

`SAM 3D Body` 기반 body reconstruction과 body-only virtual fitting AI 파트 저장소

현재 범위:

- 단일 전신 사진 기준 body reconstruction
- benchmark / dataset / artifact spec 문서
- GPU worker CLI
- official `SAM 3D Body` adapter 연결

현재 비범위:

- 얼굴 복원
- hair personalization
- full garment fitting service 완성

## Repository Structure

```text
.
├── README.md
├── docs/
├── scripts/
├── third_party/
│   └── sam-3d-body/
├── checkpoints/
└── workers/
    └── gpu-worker/
```

## Requirements

- Ubuntu Linux 권장
- Python `3.10+`
- Conda 권장
- NVIDIA GPU 권장
- 테스트 기준 GPU: `RTX 3090 24GB`
- `git`, `python`, `pip`, `rg` 설치 권장

중요:

- `SAM 3D Body` gated checkpoint access 필요
- PyTorch는 로컬 CUDA 버전에 맞는 빌드 선설치 권장

## Environment Setup

### 1. Conda 환경 생성

```bash
conda create -n bys python=3.10 -y
conda activate bys
```

### 2. PyTorch 설치

로컬 CUDA 버전에 맞는 PyTorch 선설치 권장

예시 확인:

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

### 3. Worker 로컬 패키지 설치

```bash
python -m pip install -e workers/gpu-worker
```

### 4. Official SAM 3D Body dependency 설치

```bash
bash scripts/data/install_sam3d_body_requirements.sh
```

추가 optional dependency:

- `MoGe2`
- `SAM3`
- detector / segmentor 별도 weights

## Official Repo and Checkpoints

### 1. Official repo 준비

`third_party/sam-3d-body` 경로 필요

이미 repo에 포함하지 않는 경우:

```bash
git clone https://github.com/facebookresearch/sam-3d-body.git third_party/sam-3d-body
```

### 2. Hugging Face 로그인

```bash
export HF_TOKEN=YOUR_TOKEN
hf auth login --token "$HF_TOKEN"
```

주의:

- `facebook/sam-3d-body-dinov3` access 승인 필요
- fine-grained token 사용 시 public gated repo read 권한 필요

### 3. Checkpoint 다운로드

```bash
hf download facebook/sam-3d-body-dinov3 --local-dir checkpoints/sam-3d-body-dinov3
```

다운로드 후 필요한 파일:

```text
checkpoints/sam-3d-body-dinov3/model.ckpt
checkpoints/sam-3d-body-dinov3/model_config.yaml
checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt
```

## Quick Start

### 1. Provider readiness 확인

mock provider:

```bash
PYTHONPATH=workers/gpu-worker python -m app.cli providers
```

real `sam3d` readiness:

```bash
PYTHONPATH=workers/gpu-worker \
python -m app.cli providers \
  --provider sam3d \
  --sam3d-repo-path third_party/sam-3d-body \
  --sam3d-checkpoint-path checkpoints/sam-3d-body-dinov3/model.ckpt \
  --sam3d-mhr-path checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt \
  --sam3d-detector-name none \
  --sam3d-segmentor-name none \
  --sam3d-fov-name none
```

### 2. 단일 이미지 mock 실행

```bash
mkdir -p runs

PYTHONPATH=workers/gpu-worker \
python -m app.cli run \
  --input /absolute/path/to/image.jpg \
  --output-root ./runs \
  --provider mock \
  --run-id smoke_mock
```

### 3. 단일 이미지 real `SAM 3D Body` 실행

```bash
mkdir -p runs

PYTHONPATH=workers/gpu-worker \
python -m app.cli run \
  --input /absolute/path/to/image.jpg \
  --output-root ./runs \
  --provider sam3d \
  --run-id smoke_real \
  --sam3d-repo-path third_party/sam-3d-body \
  --sam3d-checkpoint-path checkpoints/sam-3d-body-dinov3/model.ckpt \
  --sam3d-mhr-path checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt \
  --sam3d-detector-name none \
  --sam3d-segmentor-name none \
  --sam3d-fov-name none
```

### 4. Manifest batch 실행

```bash
PYTHONPATH=workers/gpu-worker \
python -m app.cli run-manifest \
  --manifest docs/datasets/templates/benchmark-manifest-template.csv \
  --image-root /absolute/path/to/images \
  --output-root ./runs \
  --provider mock \
  --run-id benchmark_mock
```

real `sam3d` manifest 예시:

```bash
PYTHONPATH=workers/gpu-worker \
python -m app.cli run-manifest \
  --manifest docs/datasets/templates/benchmark-manifest-template.csv \
  --image-root /absolute/path/to/images \
  --output-root ./runs \
  --provider sam3d \
  --run-id benchmark_real \
  --sam3d-repo-path third_party/sam-3d-body \
  --sam3d-checkpoint-path checkpoints/sam-3d-body-dinov3/model.ckpt \
  --sam3d-mhr-path checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt \
  --sam3d-detector-name none \
  --sam3d-segmentor-name none \
  --sam3d-fov-name none
```

## Output Layout

```text
{output_root}/{run_id}/{sample_id}/
├── raw-images/
├── preprocessed/
├── masks/
├── poses/
├── reconstruction/
└── reports/
```

대표 산출물:

- `reconstruction/.../raw_mesh.obj`
- `reconstruction/.../body_params.json`
- `poses/.../keypoints.json`
- `reports/.../summary.json`
- `reports/.../timings.json`

## Validation / Test

### Python compile check

```bash
python -m compileall workers/gpu-worker/app workers/gpu-worker/tests
```

### Unit smoke test

```bash
PYTHONPATH=workers/gpu-worker \
python -m unittest discover \
  -s workers/gpu-worker/tests \
  -t workers/gpu-worker
```

## Tested Local Baseline

검증 기준 예시:

- Conda env: `bys`
- Python: `3.10.19`
- GPU: `RTX 3090`
- real inference smoke test 완료
- body-only output 생성 확인

## Troubleshooting

### `checkpoint source missing`

원인:

- `model.ckpt` 또는 `mhr_model.pt` 미지정

조치:

- `--sam3d-checkpoint-path`
- `--sam3d-mhr-path`
- 또는 checkpoint 다운로드 재확인

### `403 GatedRepoError`

원인:

- Hugging Face repo access 미승인
- token 권한 부족

조치:

- gated repo access 승인
- `read` token 또는 public gated repo read 권한 확인

### `cuda unavailable`

원인:

- CUDA 미탐지
- driver / torch build mismatch

조치:

- `nvidia-smi` 확인
- `python -c "import torch; print(torch.cuda.is_available())"` 확인
- CUDA 대응 PyTorch 재설치

### `detectron2` 또는 `moge` import 실패

원인:

- optional dependency 미설치

조치:

- `scripts/data/install_sam3d_body_requirements.sh` 재실행
- optional package 수동 설치

## Important Notes

- 이 repo의 중심은 `body reconstruction`
- 얼굴 복원 경로는 제외 상태
- garment fitting은 후속 backend / blender pipeline과 결합 예정
- `checkpoints/`, `runs/`, 개인 입력 이미지 업로드 금지 권장

## Related Docs

- GPU worker 세부 문서: [workers/gpu-worker/README.md](./workers/gpu-worker/README.md)
- dataset 문서: [docs/datasets](./docs/datasets)
- benchmark 문서: [docs/benchmarks](./docs/benchmarks)
- data lifecycle 문서: [docs/data](./docs/data)
