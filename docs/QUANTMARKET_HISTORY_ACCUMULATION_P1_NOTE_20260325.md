# QUANTMARKET_HISTORY_ACCUMULATION_P1_NOTE_20260325.md

## 이번 작업 범위
시장 브리핑 서비스 고도화를 위한 누적 데이터 적재 구조를 `QuantMarket` 내부에 추가했다.

중요:
- 이번 작업은 `웹서비스 반영 전 단계`로 진행했다.
- 운영 GCS current / QuantService 소비 구조를 바꾸는 UI/표시 변경은 하지 않았다.
- 검증도 임시 snapshot/handoff 경로에서만 수행했다.

## 추가된 내부 적재 대상
- 시장 컨텍스트 이력
- AI 브리핑 이력
- publish 이력
- 자산군 상대강도 시간별 이력
- 상태 전이 통계 이력
- QuantService용 payload / API payload DB 아카이브 확장

## 추가된 테이블
- `market_context_history`
- `market_ai_brief_history`
- `market_publish_history`
- `market_asset_relative_strength_hourly`
- `market_state_transition_stats`

## 반영 파일
- `D:\QuantMarket\src\quantmarket_market\schema.py`
- `D:\QuantMarket\src\quantmarket_market\history_store.py`
- `D:\QuantMarket\src\quantmarket_market\pipeline.py`

## 검증 방식
- remote publish 비활성
- 임시 snapshot 경로: `D:\QuantMarket\_tmp\history_validation\snapshot`
- 임시 handoff 경로: `D:\QuantMarket\_tmp\history_validation\handoff`
- API 키 비활성 상태로 내부 적재 구조만 검증

## 검증 결과
- `market_context_history`: 1 row 적재 확인
- `market_ai_brief_history`: 2 row 적재 확인
- `market_publish_history`: local/remote 상태 row 적재 확인
- `market_asset_relative_strength_hourly`: 6 row 적재 확인
- `market_state_transition_stats`: 1 row 적재 확인

## 아직 하지 않은 것
- QuantService UI/route 변경
- 운영 current payload shape 변경
- 신규 시계열 API 공개
- 자산군 비교/타임라인 웹 노출

## 다음 권장 단계
1. 누적 적재를 며칠간 내부 운영하면서 데이터 품질 확인
2. 타임라인/자산군 상대강도용 API payload 설계
3. 사용자 승인 후에만 QuantService 반영 작업 진행
