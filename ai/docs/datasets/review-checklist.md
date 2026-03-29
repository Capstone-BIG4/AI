# Input Review Checklist

기준 문서: [../../../plan.md](../../../plan.md), [../../../README.md](../../../README.md), [../../../step.md](../../../step.md)  
적용 단계: Step 2  
주요 소비 주체: QA, AI 검수 담당

## 1. 사용 목적

- 샘플 1건 단위 수작업 검수 기준
- 라벨링 누락 방지
- 리뷰어 간 체크 순서 통일

## 2. 체크 순서

1. 파일 열기 가능 여부 확인
2. 단일 인물 여부 확인
3. 전신 포함 여부 확인
4. 절단, 가림, 블러, 저조도, 원근 왜곡 확인
5. `good / warning / reject` 라벨 결정
6. primary / secondary reason 선택
7. 메모 입력
8. review status 갱신

## 3. 체크리스트

| 항목 | 확인 내용 | 값 예시 |
|---|---|---|
| 파일 상태 | 열기 가능, 확장자 정상 | `ok` |
| 인물 수 | 단일 인물 여부 | `single` |
| 전신 가시성 | 머리~발끝 확인 가능 여부 | `full` |
| 머리 절단 | 없음 / 일부 / 심함 | `none` |
| 발 절단 | 없음 / 일부 / 심함 | `none` |
| 가림 | 없음 / 낮음 / 중간 / 높음 | `medium` |
| 조명 | 밝음 / 보통 / 어두움 / 매우 어두움 | `normal` |
| 블러 | 없음 / 낮음 / 중간 / 높음 | `low` |
| 배경 | 단순 / 중간 / 복잡 | `complex` |
| 원근 | 정상 / 경미 / 극단 | `normal` |
| 의복 핏 | 타이트 / 보통 / 루즈 / 매우 루즈 | `loose` |
| 최종 라벨 | good / warning / reject | `warning` |
| primary reason | taxonomy 선택 | `LOOSE_CLOTHING` |
| secondary reasons | 복수 선택 가능 | `COMPLEX_BACKGROUND` |
| 메모 | 판정 근거 | 자유 입력 |

## 4. reject 즉시 조건

- 다중 인물
- 주요 신체 구간 미포함
- severe occlusion
- heavy blur
- very dark lighting
- extreme perspective

## 5. review status 규칙

| 상태 | 의미 |
|---|---|
| `draft` | 초안 입력 상태 |
| `reviewed` | 1차 검수 완료 |
| `approved` | 2차 검수 또는 승인 완료 |
| `hold` | 판정 보류 |

## 6. 메모 예시

- `warning`: 루즈핏 상의로 허리선 식별 난도 상승
- `reject`: 발끝과 종아리 대부분 미포함
- `warning`: 배경 복잡도 높으나 인체 윤곽은 유지

## 7. 연결 문서

- [input-benchmark-spec.md](./input-benchmark-spec.md)
- [input-labeling-guide.md](./input-labeling-guide.md)
