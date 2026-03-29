# Benchmarks

기준 문서: [../../../plan.md](../../../plan.md), [../../../README.md](../../../README.md), [../../../step.md](../../../step.md)  
적용 단계: Step 2, Step 3, Step 4, Step 13

## 1. 문서 역할

### 목적

- 입력 benchmark 실행 결과 기록 위치 제공
- reconstruction baseline 보고 형식 표준화
- Step 3 이후 회귀 비교 기준점 관리

## 2. 구성 문서

- [reconstruction-benchmark-template.md](./reconstruction-benchmark-template.md): 실행 보고서 템플릿
- [templates/reconstruction-run-template.csv](./templates/reconstruction-run-template.csv): 샘플 단위 측정치 기록 템플릿

## 3. 운영 원칙

- benchmark 보고서에 모델 버전, GPU, 해상도, 배치 크기 기록 필수
- 입력셋 version과 manifest 해시 기록 필수
- 성공률, warning 비율, reject 비율, 평균 latency 동시 기록
- 수치 비교와 정성 메모 동시 보존

## 4. 연결 문서

- [../datasets/input-benchmark-spec.md](../datasets/input-benchmark-spec.md)
- [../datasets/input-labeling-guide.md](../datasets/input-labeling-guide.md)
