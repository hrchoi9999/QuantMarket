# QUANTMARKET_INTRADAY_SNAPSHOT_P0_NOTE_20260326.md

## 목적
장 종료 후 정식 시장 브리핑과 분리해서, 장중 현재 흐름을 설명하기 위한 `intraday snapshot` 레이어를 QuantMarket 내부에 추가한다.

## 이번 작업 범위
- 장중 스냅샷용 DB 테이블 추가
- 장중 지수/환율/breadth 수집기 추가
- 장중 선물/수급 보조지표 수집기 추가
- 장중 상태 계산기 추가
- admin 전용 payload 생성
- payload DB 아카이브 추가
- breadth 대체 원천 확보

## 추가된 테이블
- `market_intraday_index_snapshot`
- `market_intraday_fx_snapshot`
- `market_intraday_breadth`
- `market_intraday_futures_snapshot`
- `market_intraday_flow_signal`
- `market_intraday_state`

## 추가된 파일
- `D:\QuantMarket\src\quantmarket_market\intraday_market.py`
- `D:\QuantMarket\run_intraday_market_snapshot.py`
- `D:\QuantMarket\scripts\run_dev_intraday_market_snapshot.ps1`
- `D:\QuantMarket\scripts\register_dev_intraday_market_snapshot_task.ps1`
- `D:\QuantMarket\scripts\unregister_dev_intraday_market_snapshot_task.ps1`

## 생성되는 admin 전용 파일
- `admin_market_intraday_summary.json`
- `admin_market_intraday_detail.json`
- `admin_market_intraday_manifest.json`

## 현재 수집 전략
1. 지수/환율 1차 시도
- Yahoo chart API 기반 live 수집
- `^KS11` -> KOSPI
- `^KQ11` -> KOSDAQ
- `^KS200` -> KOSPI200
- `KRW=X` -> USD/KRW

2. breadth 수집 우선순위
- 1차: `FinanceDataReader.SnapDataReader('KRX/INDEX/STOCK/1001')`
- 1차: `FinanceDataReader.SnapDataReader('KRX/INDEX/STOCK/2001')`
- 2차: 네이버 금융 `sise_market_sum.naver` 전체 페이지 집계
  - `sosok=0` -> KOSPI
  - `sosok=1` -> KOSDAQ

3. 선물/수급 보조지표
- 선물: 네이버 금융 `sise_index.naver?code=FUT`
  - 선물 현재가 / 등락률 / 약정수량 / 약정대금 수집
  - KOSPI200 대비 상대 움직임(`현물 대비 선물 우위/약세/유사`) 계산
- 수급: 네이버 금융 시간별 순매수 iframe
  - `programDealTrendTime.naver` -> 프로그램 전체/비차익 순매수
  - `investorDealTrendTime.naver` -> 외국인/기관계 순매수
  - admin 화면에서는 `순매수 우위/순매도 우위`, `강함/보통/약함`으로 표시

4. 최종 fallback
- 지수 live까지 실패하면 최신 일별 종가를 전일 기준 참고 스냅샷으로 사용
- 이 경우 `session_status = fallback_prev_close`
- 방향 판정은 `전일 기준 참고`, `total_score = 0.0`으로 중립 처리
- breadth까지 모두 실패하면 fallback breadth를 넣고 `session_status = live_indexes_only` 또는 `fallback_prev_close`로 안내

## 성능 최적화
- 네이버 breadth 집계는 `requests.Session` 재사용으로 연결 비용을 줄입니다.
- 첫 페이지를 한 번만 읽고 마지막 페이지 수를 파악합니다.
- 2페이지 이후는 병렬 수집으로 처리해 15분 장중 스케줄 부담을 낮췄습니다.
- 최근 검증 기준 장중 스냅샷 1회 실행 시간은 약 16초 수준입니다.

## 현재 환경 검증 결과
- Yahoo chart 기반 KOSPI/KOSDAQ/KOSPI200/USDKRW live 수집 확인
- KRX breadth 호출은 현재 환경에서 `JSONDecodeError` 또는 연결 오류가 발생할 수 있음
- KRX breadth 실패 시 네이버 금융 전체 종목 페이지 집계로 대체 breadth 확보 확인
- 최신 검증 기준 source:
  - `index=yahoo_chart`
  - `fx=yahoo_chart`
  - `breadth=naver:sise_market_sum`
- admin payload 생성 및 DB 적재는 정상 확인

## 최신 검증 예시
- `asof = 2026-03-26T15:42:52+09:00`
- `session_status = live`
- `direction_label = 강한 약세`
- `KOSPI breadth = 792 상승 / 1482 하락 / 143 보합`
- `KOSDAQ breadth = 380 상승 / 1304 하락 / 136 보합`
- `FUT = 809.10 / -3.84% / 현물과 유사`
- `PROGRAM_TOTAL_NET = -16,251억원`
- `FOREIGNER_NET = -30,980억원`

## 생성 경로 예시
- admin handoff current: `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current`
- admin snapshot current: `D:\QuantMarket\service_platform\web\public_data\admin_market\current`
- 로그: `D:\QuantMarket\reports\market_analysis\logs\intraday_market_run_*.log`

## 개발단계 운영 스크립트
- 수동 실행:
  - `powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\run_dev_intraday_market_snapshot.ps1`
- 작업 등록:
  - `powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\register_dev_intraday_market_snapshot_task.ps1`
- 작업 해제:
  - `powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\unregister_dev_intraday_market_snapshot_task.ps1`

기본 스케줄:
- 평일 09:05 시작
- 15분 간격
- 6시간 30분 반복
- task name: `QuantMarket-Dev-Intraday`

## 주의
- 이 기능은 아직 admin 검토용이다.
- 공개 market 브리핑과 섞지 않는다.
- 장중 참고 레이어이며 정식 종가 브리핑을 대체하지 않는다.
- 네이버 breadth는 개발단계 대체 원천이므로, 장기 운영에서는 더 안정적인 장중 원천을 계속 검토한다.

## 다음 단계
1. 장중 선물/수급 해석 문구와 threshold 튜닝
2. 외국인/기관 외 추가 수급 프록시 확장 여부 검토
3. QS admin `/admin` 페이지 연동
4. 충분한 검토 후에만 공개 반영 검토
