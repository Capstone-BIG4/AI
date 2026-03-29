# Replan Summary

## Target

단일 전신 사진 기반 canonical body reconstruction과 3D garment fitting 중심의 body-only virtual fitting 시스템 목표

## Motivation

기존 상품 사진과 평균 마네킹만으로는 사용자 체형 차이를 반영한 핏 확인이 어렵기 때문에, 체형 기반 3D fitting 결과 제공 필요

## Problem or Challenge

- 단일 사진 기반 body proportion 오차 가능성
- garment 질감과 길이를 body reconstruction과 별도 layer로 처리해야 하는 구조
- body와 garment의 scale, axis, fitting 안정성 확보 필요

## Creative

SAM 3D Body 기반 body reconstruction을 실제 garment fitting, backend orchestration, web viewer와 연결한 end-to-end virtual fitting 구조 자체가 차별점

## Plans

- Phase 1: body reconstruction 안정화
- Phase 2: canonical body와 measurement 정리
- Phase 3: sample garment fitting PoC
- Phase 4: web demo 완성
