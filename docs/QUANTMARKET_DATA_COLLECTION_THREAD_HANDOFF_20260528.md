# QuantMarket 시장데이터수집 작업 전달서

- 작성일: 2026-05-28
- 대상 폴더: `D:\QuantMarket`
- 인수 쓰레드: `시장데이터수집 작업`
- 기존 쓰레드 역할: 시장분석 해석, 모델 개발, 성능 평가, 백테스트
- 새 쓰레드 역할: 시장 데이터 수집, 원천/중간 데이터 관리, current 산출물 갱신, 게시/검증 지원

## 작업 원칙

- 쓰기 권한은 `D:\QuantMarket`와 `D:\QuantBackup\QuantMarket`에 한정한다.
- `D:\Quant`와 `D:\QuantService`는 기본적으로 읽기 전용이다. 단, 명시된 게시/sync 작업은 정해진 대상 경로에만 쓴다.
- 모델 연구, threshold tuning, backtest, feature importance 분석은 시장분석/모델 개발 쓰레드가 담당한다.
- 데이터수집 쓰레드는 모델 로직을 임의 변경하지 않는다.
- 작업 후 git commit/push는 수행한다. 단, 압축 백업은 하루 1회만 수행한다.
- `service_platform/*/current`, `data/db`, 주요 report 산출물은 대부분 `.gitignore` 대상이다. git에는 코드/문서/일부 reference 파일만 반영된다.

## 주요 데이터 원천

| 구분 | 스크립트 | 주요 대상 | 비고 |
|---|---|---|---|
| 국내 지수/환율/금리 공식 데이터 | `collect_krx_official_market_data.py`, `collect_bok_ecos_market_data.py` | `data\db\market_analysis.db` | 시장분석 기본 원천 |
| 미국 금리 | `collect_treasury_yield_curve.py` | Treasury yield curve | 10Y 금리 등 |
| FRED | `collect_fred_global_data.py` | 매크로/금리 series | 시장환경지표 |
| BLS | `collect_bls_global_data.py` | 고용/물가 통계 | 시장환경지표 |
| BEA | `collect_bea_global_data.py` | GDP/PCE 등 | 시장환경지표 |
| EIA | `collect_eia_global_data.py` | 에너지/유가 | 시장환경지표 |
| Yahoo 글로벌 자산 | `collect_yahoo_global_assets.py` | 해외 지수/자산 | 글로벌 환경 |
| Kiwoom 수급 | `collect_kiwoom_investor_flows.py` | 투자자별/시장별 수급 | Kiwoom API 정상 동작 필요 |
| Kiwoom 수급 집계 | `recompute_kiwoom_market_flow_aggregate.py` | flow aggregate | backfill 후 재계산 |

## 정기 실행 작업

### 1. 장중 시장 스냅샷

- 목적: 장중 지수, breadth, 선물, 수급 흐름 갱신
- 기존 스크립트:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\QuantMarket\scripts\run_dev_intraday_market_snapshot.ps1 -SyncToQuantService -PublishRemote
```

- 주요 산출:
  - `D:\QuantMarket\service_platform\web\public_data\admin_market\current`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current`
  - `D:\QuantMarket\reports\market_analysis\logs`
- 점검:
  - 장중 asof가 당일인지 확인
  - Kiwoom 장애 시 수급 관련 항목은 stale 또는 누락 가능

### 2. 시장분석 public current 갱신

- 목적: Redbot/QuantService 시장 브리핑용 current JSON 생성 및 게시
- 기존 스크립트:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\QuantMarket\scripts\run_dev_market_analysis.ps1 -SyncToQuantService -PublishRemote
```

- 직접 실행 예:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_market_analysis_pipeline.py --market KR --asof 2026-05-26T23:00:00+09:00
```

- 필요 시 게시만 수행:

```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\sync_market_analysis_to_quantservice.ps1
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\publish_market_analysis_remote.py --asof YYYY-MM-DDTHH:00:00+09:00 --remote-provider gcs --remote-gcs-bucket quantservice-489808-market-analysis --remote-base-url https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current --remote-access-mode public --remote-credentials D:\QuantService\data\gcp\quantmarket-handoff-uploader.json
```

- 주요 산출:
  - `D:\QuantMarket\service_platform\web\public_data\current`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current`
  - `D:\QuantService\service_platform\web\public_data\market_analysis\current`
  - `gs://quantservice-489808-market-analysis/market_analysis/current`
- 검증:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_market_analysis_pipeline.py
```

### 3. 미국/글로벌 시장환경 갱신

- 목적: FRED/BLS/BEA/EIA/Treasury/Yahoo 기반 시장환경지표 갱신
- 기존 스크립트:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\QuantMarket\scripts\run_dev_us_live_market_environment.ps1 -SyncToQuantService -PublishRemote
```

- 주요 산출:
  - `market_environment_indicators.json`
  - `market_us_macro_panel.json`
  - 관련 history JSON
- 점검:
  - 미국 국채 10년 금리 등 최신일 확인
  - FRED/BLS/BEA/EIA collector 실패 여부 확인

### 4. Quant 모델용 market_context handoff 갱신

- 목적: Quant `model-run-only` 전에 필요한 시장분석 mart와 forecast handoff 갱신
- 실행:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_daily_market_ai_training_update.py --expected-asof YYYY-MM-DD
```

- 주요 산출:
  - `D:\QuantMarket\service_platform\ai_training\market_context\current`
  - `D:\QuantMarket\service_platform\quant_model_handoff\market_context\current`
- 필수 검증:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quant_model_handoff.py --expected-asof YYYY-MM-DD
```

- 정상 조건:
  - `ok = true`
  - `errors = []`
  - `quant_model_handoff_manifest.json`의 `asof_date`, `latest_asof_date`가 expected asof와 일치
  - `status.production_ready = true`
  - `market_forecast_ai_calibrated_daily_current.csv`에 `forecast_horizon=20d`, `market_scope=ALL/KOSPI/KOSDAQ` 3개 row 존재

## 비정기/관리 작업

### Kiwoom 수급 backfill

- 목적: 과거 투자자 수급 데이터 보강
- 실행 대상:
  - `collect_kiwoom_investor_flows.py`
  - `recompute_kiwoom_market_flow_aggregate.py`
- 원칙:
  - 연도 단위 또는 명시 기간 단위로 진행
  - backfill 후 aggregate 재계산
  - 이후 모델 재평가는 시장분석/모델 개발 쓰레드에 전달

### 국내 지수 daily backfill

- 목적: KRX/FDR 기반 지수 이력 보강
- 실행:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\scripts\backfill_market_index_daily_fdr.py
```

### 로컬 백업

- 경로: `D:\QuantBackup\QuantMarket`
- 원칙: 하루 1회만 압축 zip + git bundle 생성
- 기존 스크립트:

```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantBackup\QuantMarket\backup_quantmarket.ps1
```

- 작업마다 백업하지 않는다.
- 같은 날 이미 `QuantMarket_YYYYMMDD_HHMMSS.zip`이 있으면 생략한다.

## 수집 쓰레드가 하지 않을 작업

- flow model 성능 개선
- label/threshold tuning
- backtest 전략 해석
- feature importance 및 오류 구간 분석
- 모델 후보 조합 탐색
- 투자 판단 문구 변경
- 분석 로직 변경

위 작업은 시장분석 및 모델 개발 쓰레드가 담당한다.

## 수집 쓰레드가 분석 쓰레드에 전달할 내용

- 어떤 원천 데이터가 언제까지 갱신됐는지
- collector 실패 여부와 실패 원인
- Kiwoom/API/FRED 등 외부 서비스 장애 여부
- current/handoff asof와 production_ready 상태
- stale 데이터 또는 proxy 사용 여부
- backfill 완료 범위
- 모델 재평가가 필요한 데이터 변경 여부

## 현재 인수 시 주의점

- 2026-05-26 기준 Quant 모델 handoff는 갱신 및 검증 완료된 상태다.
- 2026-05-27 기준 시장분석/Quant handoff는 다음 작업일에 별도 실행해야 한다.
- Quant read-only DB 접근과 AI/GCS 네트워크 호출은 sandbox 안에서 실패할 수 있으므로 필요 시 escalated 실행이 필요하다.
- QuantService 게시는 로컬 sync와 GCS remote publish를 구분해 확인해야 한다.

## 최소 점검 명령

```powershell
git status --short
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_market_analysis_pipeline.py
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quant_model_handoff.py --expected-asof YYYY-MM-DD
```

