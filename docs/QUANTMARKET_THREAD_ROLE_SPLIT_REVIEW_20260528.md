# QuantMarket 쓰레드 역할 분담 의견서

작성일: 2026-05-28

검토 대상:
- `docs/QUANTMARKET_DATA_COLLECTION_THREAD_HANDOFF_20260528.md`
- 기존 QuantMarket 시장 데이터 업데이트 구조
- Quant 모델 handoff 운영 흐름

## 결론

시장데이터수집 쓰레드는 데이터 수집, 확정 파이프라인 실행, current 산출물 갱신, 게시 및 검증만 담당한다.

시장분석 쓰레드는 분석 로직, 모델 연구, 성능 해석, 백테스트, 백업 정책 및 백업 실행을 담당한다.

현재 작업분담 문서는 큰 방향은 맞지만, 일부 데이터 소스와 실행 wrapper가 누락되었고, 백업 담당 주체를 시장분석 쓰레드로 명확히 옮겨 적는 보정이 필요하다.

## 시장데이터수집 쓰레드 담당

### 정기 데이터 수집

- KRX 공식 시장 데이터 수집
- BOK ECOS 금리/거시 데이터 수집
- Treasury yield curve 수집
- FRED 글로벌 거시 데이터 수집
- BLS 글로벌 지표 수집
- BEA 글로벌 지표 수집
- EIA 에너지 데이터 수집
- Yahoo global assets intraday/current 수집
- Kiwoom 투자자 수급 데이터 수집
- Kiwoom 시장 수급 aggregate 재계산
- Google News RSS 기반 시장 뉴스 입력 갱신
- DART 공시 요약 입력 갱신

### 확정 파이프라인 실행

- 시장브리핑/시장분석/시장 환경 지표용 public current 갱신
- intraday market snapshot 갱신
- US/global market environment current 갱신
- Quant model market context / forecast handoff 갱신

### 게시 및 검증

- `D:\QuantMarket` 산출물 생성
- 명시된 경우에만 `D:\QuantService` public data sync
- 명시된 경우에만 GCS current publish
- Quant handoff validation 실행
- QuantService public handoff validation 실행

## 시장분석 쓰레드 담당

- 시장 상태 산식 변경
- 모델 feature 변경
- label, threshold, calibration 변경
- backtest 및 성능 평가
- feature importance / error-zone 분석
- 투자 문구, 해석 문구, UI 표현 정책 변경
- 신규 분석 payload 설계
- 데이터 백업 정책 수립
- `D:\QuantBackup\QuantMarket` 백업 실행 및 검증

## 보정이 필요한 항목

### 1. 백업 담당 변경

기존 handoff 문서의 백업 항목은 시장데이터수집 쓰레드가 아니라 시장분석 쓰레드 담당으로 명시한다.

권장 문구:

```text
백업은 시장분석 쓰레드가 담당한다. 시장데이터수집 쓰레드는 백업 실행을 기본 업무로 수행하지 않으며, 백업 전 필요한 데이터 freshness 확인만 지원한다.
```

### 2. public current 갱신 wrapper 명확화

운영 기준 명령은 아래 wrapper를 우선 문서화한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\run_dev_market_analysis_publish_remote.ps1
```

`run_dev_market_analysis.ps1`는 하위 실행 wrapper로 볼 수 있으나, remote publish까지 포함한 정기 운영 기준은 `run_dev_market_analysis_publish_remote.ps1`가 더 명확하다.

### 3. Google News RSS 누락

시장브리핑, AI brief, next-day preview 입력으로 쓰이는 뉴스 수집/요약 흐름을 데이터수집 담당에 포함한다.

### 4. DART 공시 요약 누락

DART 공시 요약은 시장분석 public payload의 입력 데이터다. API key 미설정 시 optional/fallback 상태로 두더라도 담당 범위에는 포함한다.

### 5. US/global 환경 갱신 설명 분리

`run_dev_us_live_market_environment.ps1`는 Yahoo intraday 수집과 environment current 재생성이 중심이다.

FRED/BLS/BEA/EIA/Treasury의 전체 갱신은 별도 collector 또는 daily market AI training update 흐름으로 분리해 적는다.

### 6. 수동 reference/fallback 파일 관리 추가

아래 파일은 데이터 freshness와 fallback 품질에 영향을 주므로 관리 대상으로 명시한다.

- `D:\QuantMarket\data\reference\kr_rates_manual_seed.csv`
- `D:\QuantMarket\data\reference\market_ai_briefs_manual.json`

### 7. Quant read-only 의존성 명시

시장데이터수집 쓰레드는 `D:\Quant`를 수정하지 않는다. 단, 아래 데이터는 read-only 입력으로 확인할 수 있다.

- `D:\Quant\data\db\price.db`
- `D:\Quant\data\db\regime.db`
- `D:\Quant\data\universe`

### 8. commit/push 범위 제한

routine 데이터 갱신 후 generated current, DB, report 파일을 무조건 commit/push하지 않는다.

권장 문구:

```text
git commit/push는 문서, 코드, reference 설정 변경에 한해 수행한다. routine generated output은 원칙적으로 커밋 대상이 아니다.
```

## 시장데이터수집 쓰레드에서 하지 않을 일

- 분석 로직 변경
- 모델 튜닝
- threshold/label 변경
- backtest 설계 또는 해석
- 모델 성능 개선 실험
- 투자 판단 문구 변경
- UI 표현 정책 변경
- 백업 실행

## Quant handoff 운영 경계

Quant model handoff는 시장데이터수집 쓰레드가 실행 및 검증할 수 있다.

다만 아래 작업은 시장분석 쓰레드 담당이다.

- handoff 모델 로직 변경
- forecast calibration 방식 변경
- AI 모델 성능 비교 해석
- horizon/scope 정책 변경

시장데이터수집 쓰레드는 아래 조건 확인까지만 담당한다.

- `manifest.asof_date` 일치
- `production_ready = true`
- required forecast horizon row 존재
- `validate_quant_model_handoff.py` 통과

## 권장 최종 역할 정의

```text
시장데이터수집 쓰레드:
원천 데이터와 확정 운영 파이프라인을 최신 상태로 유지하고, redbot.co.kr 및 Quant 모델이 소비하는 current/handoff 산출물을 생성, 게시, 검증한다.

시장분석 쓰레드:
시장 데이터의 해석, 모델/산식 개선, 백테스트, 성능 평가, 정책 판단, 백업 운영을 담당한다.
```
