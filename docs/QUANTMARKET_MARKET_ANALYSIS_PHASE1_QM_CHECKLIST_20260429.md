# QuantMarket 시장 분석 1차 QM 완료 체크리스트

작성일: 2026-04-29

## 목표
- QS가 `시장 분석` 메뉴를 바로 구현할 수 있도록
- QM에서 탭 구조, payload 계약, 공개 URL, 안내 데이터까지 선행 완료한다.

## 1. 탭 구조 확정
- [x] `시장 상태`
- [x] `자산 강도`
- [x] `장중/야간 참고`
- [x] `데이터 해설`

## 2. 기존 current/history payload 확인
- [x] timeline current/history
- [x] asset strength current/history
- [x] state transition current/history
- [x] next-day preview current/history

## 3. 시장 분석 1차 전용 payload 추가
- [x] `quantservice_market_analysis_tabs.json`
- [x] `quantservice_market_live_context.json`
- [x] `quantservice_market_data_guide.json`
- [x] API wrapper 생성
  - `api_v1_market_analysis_tabs.json`
  - `api_v1_market_analysis_live_context.json`
  - `api_v1_market_analysis_data_guide.json`

## 4. manifest 계약 반영
- [x] optional_files에 신규 파일 반영
- [x] API endpoint 목록 반영
- [x] 공개형 non-advisory note 유지

## 5. publish 경로 반영
- [x] local snapshot 생성
- [x] quantservice handoff 생성
- [x] remote publish 목록 반영

## 6. QS 연결 준비 상태
- [x] 탭별 current/history 파일 이름 확정
- [x] 장중/야간 참고용 전용 current payload 제공
- [x] 데이터 해설 탭용 payload 제공
- [x] source tier 설명 payload 제공

## 7. 다음 단계
- [x] pipeline 재실행 후 payload 생성 확인
- [x] GCS 공개 URL 확인
- [x] QS-Master 요청서 최신화
- [x] DART / KRX 상세 / 미국시장 패널 2차 범위 정리
