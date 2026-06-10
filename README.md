# Virtual Fitting Studio

SAM 3D Body 기반 가상 피팅 캡스톤 데모입니다. 사용자의 전신 사진 1장과 상의 앞/뒤, 하의 앞/뒤 이미지를 입력받고, SAM으로 추정한 신체 비율과 가이드맵을 기반으로 2D 피팅 결과와 front / side / back 2.5D 마네킹 뷰어를 제공합니다.

## 주요 기능

- 전신 사진, 상의 앞/뒤, 하의 앞/뒤 총 5장 업로드
- 업로드 후 `Run Fitting`으로 피팅 플로우 실행
- 2D 가상 피팅 결과 확인
- `3D Viewer`에서 front / side / back 마네킹 피팅 결과 전환
- `Analytics` 화면에서 SAM Body, guide map, 최종 결과 흐름 확인

## 실행 방법

### 1. 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

이미 `conda` 환경을 쓰는 경우에는 가상환경 생성 없이 해당 환경에서 설치해도 됩니다.

```bash
conda activate bys
python -m pip install -r requirements.txt
```

### 2. 웹 UI 실행

```bash
python scripts/dev/run_server.py --port 8000
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

### 3. GPU 파이프라인 실행

GPU에서 실제 생성 단계를 실행하려면 `.env`를 준비합니다.

```bash
cp .env.example .env
```

`.env` 예시:

```env
HF_TOKEN=
FASHN_API_KEY=
CONDA_ENV=bys
SAM3D_BODY_DIR=external/sam-3d-body
FASHN_WEIGHTS_DIR=external/fashn-vton-1.5/weights
```

SAM 3D Body 공식 소스는 아래처럼 연결합니다.

```bash
git clone https://github.com/facebookresearch/sam-3d-body.git external/sam-3d-body
```

주요 생성 단계:

```bash
python scripts/18_build_sam_body_only_mannequin_base.py
python scripts/19_generate_sam_body_only_fashn_viewer.py --views front back side --seeds 2101 2201
python scripts/20_select_sam_body_only_viewer.py
python scripts/10_guard_viewer_contract.py
```

웹 UI에서는 실행 모드를 `GPU`로 선택한 뒤 `Run Fitting`을 누르면 백엔드가 설정된 파이프라인 단계를 순서대로 실행합니다.

## 검증 방법

```bash
make check
```

conda 환경을 지정해서 실행하려면:

```bash
make check PYTHON="conda run -n bys python"
```

검증 항목:

- 프론트엔드/백엔드 필수 파일 존재 여부
- 결과 이미지 dimension 확인
- `assets/manifest.json` 경로 무결성 확인
- viewer 결과 contract 확인
- 공개 파일 내 비밀값 포함 여부 확인

## 문서

- [개발자 가이드](docs/developer-guide.md)
- [기술 파이프라인](docs/technical-pipeline.md)
- [모델 노트](docs/model-cards-used.md)
- [코드 리뷰 노트](docs/code-review.md)

## 라이선스

MIT License
