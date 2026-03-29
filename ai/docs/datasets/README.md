# Datasets

기준 문서: [../../../plan.md](../../../plan.md), [../../../README.md](../../../README.md), [../../../step.md](../../../step.md)  
적용 단계: Step 2, Step 3, Step 13

## 1. 문서 역할

### 목적

- 입력 benchmark 세트 관리 기준
- 샘플 라벨링 규칙 연결 허브
- manifest와 체크리스트 위치 안내
- Step 3 회귀 테스트 입력셋 기준점 제공

## 2. 구성 문서

- [input-benchmark-spec.md](./input-benchmark-spec.md): 샘플셋 범위, 최소 수량, 디렉터리 구조, naming 규칙
- [input-labeling-guide.md](./input-labeling-guide.md): `good / warning / reject` 라벨 규칙, failure reason taxonomy, 리뷰 정책
- [review-checklist.md](./review-checklist.md): 샘플 1건 단위 수작업 검수 체크리스트
- [templates/benchmark-manifest-template.csv](./templates/benchmark-manifest-template.csv): 샘플 manifest 템플릿

## 3. 권장 디렉터리 구조

```text
ai/docs/datasets/
├── README.md
├── input-benchmark-spec.md
├── input-labeling-guide.md
├── review-checklist.md
└── templates/
    └── benchmark-manifest-template.csv
```

## 4. 운영 원칙

- 원본 이미지 바이너리의 Git 직접 커밋 지양
- 실제 이미지 저장 위치와 문서 manifest 분리
- 샘플 ID, 품질 라벨, failure reason의 고정 필드 유지
- Step 3 이후 회귀 테스트 입력셋 변경 시 version 기록 필수
- 개인정보와 동의 범위 확인 없는 외부 이미지 사용 금지

## 5. 연결 문서

- [../benchmarks/README.md](../benchmarks/README.md)
- [../../../backend/docs/object-storage-spec.md](../../../backend/docs/object-storage-spec.md)
- [../data/artifact-lifecycle.md](../data/artifact-lifecycle.md)
