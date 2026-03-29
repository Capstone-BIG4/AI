# GPU Worker

Step 3 기준 GPU worker 초안 구현 상태

## 책임 범위

- input validation
- preprocessing
- pose / body reconstruction entrypoint
- artifact 저장
- benchmark manifest 실행
- Step 4 이전 raw reconstruction 결과 저장

## 현재 구현 상태

- `mock` provider 기반 reconstruction CLI 동작
- 단일 이미지 실행 지원
- manifest CSV 기반 다건 실행 지원
- artifact 디렉터리 생성 지원
- validation / timings / summary / benchmark CSV 출력 지원
- 공식 `SAM 3D Body` repo checkout 연동 구조 반영
- local checkpoint 또는 Hugging Face checkpoint source 선택 구조 반영
- official detector / segmentor / fov 설정 경로 반영
- readiness report 출력 지원

## 현재 비범위

- 실제 SAM 3D Body 추론 성공 보장
- CUDA 기반 VRAM 측정
- canonicalization
- measurement extraction

## 실행 예시

단일 이미지 실행:

```bash
PYTHONPATH=ai/workers/gpu-worker \
python -m app.cli run \
  --input /path/to/image.jpg \
  --output-root /path/to/output \
  --provider mock
```

manifest 실행:

```bash
PYTHONPATH=ai/workers/gpu-worker \
python -m app.cli run-manifest \
  --manifest ai/docs/datasets/templates/benchmark-manifest-template.csv \
  --image-root /path/to/images \
  --output-root /path/to/output \
  --provider mock
```

provider 확인:

```bash
PYTHONPATH=ai/workers/gpu-worker python -m app.cli providers
```

공식 repo readiness 확인:

```bash
PYTHONPATH=ai/workers/gpu-worker \
python -m app.cli providers \
  --provider sam3d \
  --sam3d-repo-path ai/third_party/sam-3d-body \
  --sam3d-checkpoint-path /path/to/model.ckpt \
  --sam3d-mhr-path /path/to/mhr_model.pt
```

공식 repo 실행 예시:

```bash
PYTHONPATH=ai/workers/gpu-worker \
python -m app.cli run \
  --input /path/to/image.jpg \
  --output-root /path/to/output \
  --provider sam3d \
  --sam3d-repo-path ai/third_party/sam-3d-body \
  --sam3d-checkpoint-path /path/to/model.ckpt \
  --sam3d-mhr-path /path/to/mhr_model.pt \
  --sam3d-detector-name vitdet \
  --sam3d-segmentor-name sam2 \
  --sam3d-segmentor-path /path/to/sam2 \
  --sam3d-fov-name moge2
```

## 출력 구조

```text
{output_root}/{run_id}/{sample_id}/
├── raw-images/
├── preprocessed/
├── masks/
├── poses/
├── reconstruction/
└── reports/
```

## 다음 연결 단계

- Step 3 후반: 공식 SAM 3D Body adapter 연결
- Step 4: canonicalization / measurement 계층 추가

## 공식 연동 기준

- 공식 repo checkout 위치: `ai/third_party/sam-3d-body`
- 공식 참고 파일: `README.md`, `INSTALL.md`, `demo.py`, `notebook/utils.py`
- core API: `load_sam_3d_body`, `SAM3DBodyEstimator`
- checkpoint source:
  - local `model.ckpt` + `mhr_model.pt`
  - Hugging Face repo id fallback
- optional components:
  - detector: `vitdet` 또는 `sam3`
  - segmentor: `sam2`, `sam3`, `none`
  - fov: `moge2`, `none`

## 현재 blocker

- `bys` 환경 기준 공식 core import 실패
- 확인된 누락 예시: `braceexpand`, `yacs`, `einops`, `hydra`, `pyrootutils`, `detectron2`
- CUDA device 미탐지 상태
- checkpoint와 MHR asset 미지정 상태
