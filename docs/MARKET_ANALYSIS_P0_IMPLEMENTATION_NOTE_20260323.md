# QuantMarket 시장분석 P0 구현 메모

## 이번 구현 범위

- `market_analysis.db` 초기 스키마 구현
- 공식 지표 저장 테이블과 분석/상태/payload 계층 분리
- `run_market_analysis_pipeline.py` 오케스트레이션 엔트리 구현
- 4개 컴포넌트 점수와 7단계 상태 매핑 구현
- summary/detail/today_bridge/manifest snapshot 생성 구현
- `--seed-sample` 기반 end-to-end 검증 경로 제공

## 현재 P0 구현 특징

- 원천 데이터 테이블:
  - `market_index_daily`
  - `market_fx_daily`
  - `market_rates_daily`
- 분석 계층 테이블:
  - `market_features_hourly`
  - `market_component_scores`
  - `market_state_history`
- 서비스 계층 테이블:
  - `market_analysis_payload`
  - `market_analysis_ai_notes`

## 중요한 가정

- breadth 원천 데이터가 아직 `D:\QuantMarket`에 없어서, 현재는 KOSPI/KOSDAQ/KOSPI200 기반 프록시를 사용한다.
- 방어자산 선호도도 현재는 환율/금리/지수 역방향 프록시 중심으로 계산한다.
- 실제 내부 breadth / ETF 상대강도 데이터가 준비되면 같은 스키마에 그대로 대체 가능하다.
- AI 해설은 아직 비활성 기본값(`enabled=false`)만 넣는다.

## 실행 예시

```powershell
python D:\QuantMarket\run_market_analysis_pipeline.py --market KR --asof 2026-03-23T14:00:00+09:00 --seed-sample
```

## 산출 위치

- DB: `D:\QuantMarket\data\db\market_analysis.db`
- snapshot:
  - `D:\QuantMarket\service_platform\market_analysis\market_analysis_summary.json`
  - `D:\QuantMarket\service_platform\market_analysis\market_analysis_detail.json`
  - `D:\QuantMarket\service_platform\market_analysis\market_analysis_today_bridge.json`
  - `D:\QuantMarket\service_platform\market_analysis\market_analysis_manifest.json`
