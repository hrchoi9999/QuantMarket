# QuantMarket 반복 자동실행 작업 이관 응답서

- 작성일: 2026-05-23
- 대상 요청서: `D:\QuantOpsScheduler\state\work-requests\20260522-154012-all-threads-automation-transfer-survey.md`
- 대상 쓰레드/프로젝트명: QuantMarket
- 작업 폴더: `D:\QuantMarket`
- 응답 기준: 반복적으로 일정 시간에 실행되는 자동작업만 본문 이관 대상으로 작성

## 1. 기본 정보

- 담당 목적: 시장분석 payload 생성, 장중 snapshot 갱신, 야간 글로벌 시장환경 갱신, 로컬 백업
- 현재 자동실행 여부: ACTIVE
- 현재 등록 방식: Windows 작업 스케줄러
- 기본 Python/venv: `D:\Quant\venv64\Scripts\python.exe`
- 쓰기 허용 위치:
  - `D:\QuantMarket`
  - `D:\QuantBackup\QuantMarket`
- 읽기 전용 참조 위치:
  - `D:\Quant`
  - `D:\QuantService`
- 이관 원칙:
  - QuantOpsScheduler 통합 자동실행 검증 완료 전까지 기존 작업은 중지하지 않음
  - 통합 완료 고지 후 QuantMarket 쓰레드에서 기존 Windows 작업 스케줄러 작업을 중지
  - 허브는 외부 폴더 직접 수정 대신 실행 상태/산출물 검증 중심으로 관리 권장

## 2. 자동실행 작업 목록

### 작업 A

- 작업 이름: QuantMarket full hourly market-analysis publish
- 작업 ID 또는 기존 자동실행 ID: `QuantMarket-Dev-Hourly`
- 현재 상태: Ready
- 실행 주기: 매시간 1회
- 실행 시간대: 매시 05분 KST
- 실행 조건: PC 켜짐, 네트워크 가능, GCS credentials 접근 가능
- 실행 명령:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\QuantMarket\scripts\run_dev_market_analysis_publish_remote.ps1
```

- 작업 디렉터리: `D:\QuantMarket`
- 사용하는 Python/venv/도구:
  - `D:\Quant\venv64\Scripts\python.exe`
  - PowerShell
  - GCS credential: `D:\QuantService\data\gcp\quantmarket-handoff-uploader.json`
- 필요한 입력 파일:
  - `D:\QuantMarket\data\reference\kr_rates_manual_seed.csv`
  - `D:\QuantMarket\data\reference\market_ai_briefs_manual.json`
  - `D:\Quant` read-only reference data
- 읽는 DB/테이블:
  - `D:\QuantMarket\data\db\market_analysis.db`
  - `D:\Quant\data\db\price.db` read-only
  - 기타 `D:\Quant` breadth/regime/relative-strength read-only sources
- 쓰는 DB/테이블:
  - `D:\QuantMarket\data\db\market_analysis.db`
- 수정/생성하는 파일:
  - `D:\QuantMarket\service_platform\web\public_data\current\*.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\*.json`
  - `D:\QuantMarket\reports\market_analysis\logs\market_analysis_run_*.log`
  - 원격 GCS: `gs://quantservice-489808-market-analysis/market_analysis/current`
- 외부 API/네트워크 의존성:
  - 공식 시장데이터 source
  - GCS upload
  - AI brief 생성 경로 사용 시 외부 AI API 가능
- 정상 완료 판단 기준:
  - exit code `0`
  - 로그에 `Completed QuantMarket full hourly pipeline`
  - current/handoff JSON 갱신
  - GCS publish 성공
- 실패 판단 기준:
  - non-zero exit code
  - GCS publish 실패
  - `market_analysis.db` 쓰기 실패
  - output manifest/current JSON 미갱신
- 실패 시 사용자에게 알려야 하는 조건:
  - 2회 이상 연속 실패
  - current/handoff가 2시간 이상 stale
  - 원격 publish 실패
- 평균 실행 시간: 수분 이내, 외부 API/AI 호출 시 변동
- 중복 실행 허용 여부: 불허
- 동시 실행 방지:
  - `D:\QuantMarket\reports\market_analysis\logs\locks\public_publish.lock`
  - lock age 90분 미만이면 정상 skip

### 작업 B

- 작업 이름: QuantMarket intraday market snapshot and public briefing refresh
- 작업 ID 또는 기존 자동실행 ID: `QuantMarket-Dev-Intraday`
- 현재 상태: Ready
- 실행 주기: 주중 10분 간격
- 실행 시간대: 월-금 09:00~15:40 KST
- 실행 조건: 국내 장중, PC 켜짐, 네트워크 가능
- 실행 명령:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\QuantMarket\scripts\run_dev_intraday_market_snapshot.ps1 -SyncToQuantService -PublishRemote
```

- 작업 디렉터리: `D:\QuantMarket`
- 사용하는 Python/venv/도구:
  - `D:\Quant\venv64\Scripts\python.exe`
  - PowerShell
  - GCS credential
- 필요한 입력 파일:
  - `D:\QuantMarket\data\db\market_analysis.db`
  - `D:\Quant` read-only references
- 읽는 DB/테이블:
  - `D:\QuantMarket\data\db\market_analysis.db`
  - `D:\Quant` read-only market/portfolio context
- 쓰는 DB/테이블:
  - 필요 시 `D:\QuantMarket\data\db\market_analysis.db`
- 수정/생성하는 파일:
  - `D:\QuantMarket\service_platform\web\public_data\admin_market\current\*.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current\*.json`
  - `D:\QuantMarket\service_platform\web\public_data\current\*.json`
  - `D:\QuantMarket\reports\market_analysis\logs\intraday_market_run_*.log`
  - 원격 GCS
- 외부 API/네트워크 의존성:
  - 장중 시장데이터 source
  - GCS upload
- 정상 완료 판단 기준:
  - exit code `0`
  - 로그에 `Completed QuantMarket intraday snapshot and public briefing refresh`
  - admin/current/public handoff 갱신
- 실패 판단 기준:
  - non-zero exit code
  - intraday snapshot 생성 실패
  - public briefing refresh 실패
  - GCS publish 실패
- 실패 시 사용자에게 알려야 하는 조건:
  - 장중 2회 이상 연속 실패
  - 장중 public/admin handoff가 30분 이상 stale
- 평균 실행 시간: 1~3분
- 중복 실행 허용 여부: 불허
- 동시 실행 방지:
  - `public_publish.lock`
  - lock active 시 snapshot만 완료하고 public refresh skip 가능

### 작업 C

- 작업 이름: QuantMarket US/global live market environment refresh
- 작업 ID 또는 기존 자동실행 ID: `QuantMarket-Dev-US-Live`
- 현재 상태: Ready
- 실행 주기: 주중 10분 간격
- 실행 시간대: 월-금 20:00~익일 06:00 KST
- 실행 조건: 미국/글로벌 시장 시간대, PC 켜짐, 네트워크 가능
- 실행 명령:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\QuantMarket\scripts\run_dev_us_live_market_environment.ps1 -SyncToQuantService -PublishRemote
```

- 작업 디렉터리: `D:\QuantMarket`
- 사용하는 Python/venv/도구:
  - `D:\Quant\venv64\Scripts\python.exe`
  - Yahoo/global asset collector
  - GCS credential
- 필요한 입력 파일:
  - `D:\QuantMarket\data\db\global_market_context.db`
  - `D:\QuantMarket\data\db\market_analysis.db`
- 읽는 DB/테이블:
  - `global_asset_daily`
  - `global_asset_intraday_snapshot`
  - `global_asset_registry`
  - `global_context_daily`
  - QuantMarket market-analysis tables
- 쓰는 DB/테이블:
  - `D:\QuantMarket\data\db\global_market_context.db`
- 수정/생성하는 파일:
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\quantservice_market_environment_indicators.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\api_v1_market_environment_indicators.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\quantservice_market_environment_indicators_manifest.json`
  - `D:\QuantMarket\service_platform\web\public_data\current\market_environment_indicators.json`
  - `D:\QuantMarket\reports\market_environment_live\logs\us_live_market_environment_*.log`
  - 원격 GCS
- 외부 API/네트워크 의존성:
  - Yahoo/global market data
  - GCS upload
- 정상 완료 판단 기준:
  - exit code `0`
  - 로그에 `Completed QuantMarket US live market environment refresh`
  - market environment payload 3종 갱신
- 실패 판단 기준:
  - non-zero exit code
  - Yahoo/global data 수집 실패
  - GCS publish 실패
- 실패 시 사용자에게 알려야 하는 조건:
  - 야간 세션 중 2회 이상 연속 실패
  - market environment payload가 30분 이상 stale
- 평균 실행 시간: 1~3분
- 중복 실행 허용 여부: 불허
- 현재 특이사항:
  - 최근 조회 시 `LastTaskResult = 2147946720`
  - 이관 전 실행 계정/권한 확인 필요

### 작업 D

- 작업 이름: QuantMarket local backup
- 작업 ID 또는 기존 자동실행 ID: `QuantMarket-Daily-Backup`
- 현재 상태: Ready
- 실행 주기: 매일 1회
- 실행 시간대: 매일 20:40 KST
- 실행 조건: PC 켜짐, `D:\QuantBackup\QuantMarket` 쓰기 가능
- 실행 명령:

```powershell
powershell.exe -ExecutionPolicy Bypass -File "D:\QuantBackup\QuantMarket\backup_quantmarket.ps1"
```

- 작업 디렉터리: 임의
- 사용하는 Python/venv/도구:
  - PowerShell
  - robocopy
  - .NET ZipFile
  - git bundle
- 필요한 입력 파일:
  - `D:\QuantMarket` 전체
- 읽는 DB/테이블:
  - 백업 대상 파일로 포함되는 QuantMarket DB 파일
- 쓰는 DB/테이블: 없음
- 수정/생성하는 파일:
  - `D:\QuantBackup\QuantMarket\QuantMarket_YYYYMMDD_HHMMSS.zip`
  - `D:\QuantBackup\QuantMarket\QuantMarket_git_YYYYMMDD_HHMMSS.bundle`
  - `D:\QuantBackup\QuantMarket\latest_quantmarket_backup.txt`
- 외부 API/네트워크 의존성: 없음
- 정상 완료 판단 기준:
  - zip 생성
  - git bundle 생성
  - `latest_quantmarket_backup.txt`에 `git_bundle_created=True`
- 실패 판단 기준:
  - robocopy exit code > 7
  - zip 생성 실패
  - git bundle 생성 실패
- 실패 시 사용자에게 알려야 하는 조건:
  - 백업 생성 실패
  - 최신 백업이 24시간 이상 없음
- 평균 실행 시간: 약 2분
- 중복 실행 허용 여부: 불허
- 보존 정책:
  - 현재 자동 삭제 정책 없음
  - 통합 시 최근 30일 또는 최근 30개 보존 정책 권장

## 3. 최종 산출물 요구사항

### 산출물 A

- 산출물 이름: Market analysis public handoff
- 산출물 형식: JSON
- 산출물 현재 위치:
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current`
  - `D:\QuantMarket\service_platform\web\public_data\current`
- 허브에 공유해야 할 위치:
  - 허브는 위 경로를 읽기 전용으로 확인
  - summary는 `D:\QuantOpsScheduler\state\shared-data\quantmarket-latest-status.json` 권장
- 최신 상태 판정 기준:
  - generated_at/manifest가 최근 2시간 이내
  - JSON parse 가능
- 보존 기간: current 최신본, logs는 로컬 보존
- 후속 소비 쓰레드: QuantService
- 후속 소비 방식: 파일 handoff 또는 GCS remote handoff

### 산출물 B

- 산출물 이름: Admin/intraday market snapshot
- 산출물 형식: JSON
- 산출물 현재 위치:
  - `D:\QuantMarket\service_platform\web\public_data\admin_market\current`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current`
- 허브에 공유해야 할 위치: summary만 허브 shared-data에 저장 권장
- 최신 상태 판정 기준: 장중 30분 이내 generated_at
- 보존 기간: current 최신본
- 후속 소비 쓰레드: QuantService
- 후속 소비 방식: 파일 handoff/GCS

### 산출물 C

- 산출물 이름: Market environment indicators
- 산출물 형식: JSON
- 산출물 현재 위치:
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\quantservice_market_environment_indicators.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\api_v1_market_environment_indicators.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\quantservice_market_environment_indicators_manifest.json`
- 허브에 공유해야 할 위치: summary만 허브 shared-data에 저장 권장
- 최신 상태 판정 기준: 야간 세션 중 30분 이내 generated_at
- 보존 기간: current 최신본
- 후속 소비 쓰레드: QuantService public web
- 후속 소비 방식: remote JSON/GCS

### 산출물 D

- 산출물 이름: QuantMarket local backup
- 산출물 형식: ZIP / git bundle / latest metadata TXT
- 산출물 현재 위치:
  - `D:\QuantBackup\QuantMarket`
- 허브에 공유해야 할 위치:
  - `D:\QuantBackup\QuantMarket\latest_quantmarket_backup.txt`를 읽기 전용 확인
- 최신 상태 판정 기준:
  - latest backup이 24시간 이내
  - `git_bundle_created=True`
- 보존 기간:
  - 현재 제한 없음
  - 허브 이관 시 최근 30일 또는 최근 30개 보존 정책 권장
- 후속 소비 쓰레드: 복구/운영관리 쓰레드
- 후속 소비 방식: 수동 복구 또는 git bundle restore

## 4. 허브 이관 가능 범위

- 권장:
  - 허브가 반복 실행 스케줄과 실행 로그를 통합 관리
  - 허브가 산출물 manifest/status만 읽어서 shared-data에 요약 저장
  - 허브가 실패 시 해당 쓰레드에 작업요청서 생성
- 비권장:
  - 허브가 직접 `D:\QuantMarket` DB/파일 수정
  - 허브가 직접 `D:\Quant` 또는 `D:\QuantService`에 쓰기
- 통합 완료 후 기존 Windows 작업 스케줄러 중지 대상:
  - `QuantMarket-Dev-Hourly`
  - `QuantMarket-Dev-Intraday`
  - `QuantMarket-Dev-US-Live`
  - `QuantMarket-Daily-Backup`

## 5. 제약 및 주의사항

- 장중/장마감 등 시간 제약:
  - intraday: 월-금 09:00~15:40 KST
  - US/global live: 월-금 20:00~익일 06:00 KST
  - full hourly: 매시 05분
  - backup: 매일 20:40 KST
- 휴장일 처리:
  - 현재 스케줄러는 휴장일을 별도 skip하지 않음
  - 허브에서 KRX/US 휴장일 기준 정상 skip 판정 권장
- 데이터 무결성 조건:
  - current JSON parse 가능
  - manifest/generated_at stale 여부 확인
  - 원격 publish 사용 시 GCS 최신 파일 확인
- 재실행 시 주의사항:
  - 중복 실행 금지
  - `public_publish.lock` 확인
  - stale lock은 90분 기준으로 제거 가능
- 잠금 파일 또는 동시 실행 방지 장치:
  - `D:\QuantMarket\reports\market_analysis\logs\locks\public_publish.lock`
- 수동 확인이 필요한 케이스:
  - GCS credential 만료/권한 오류
  - 외부 API 시스템 점검
  - `QuantMarket-Dev-US-Live`의 `LastTaskResult=2147946720` 재발

## 6. 요청하는 통합 자동실행 결과

- 필요한 통합 결과 파일:
  - `D:\QuantOpsScheduler\state\automation-registry.json`
  - `D:\QuantOpsScheduler\state\shared-data\latest-automation-registry.json`
  - `D:\QuantOpsScheduler\state\integrated-automation-plan.json`
  - `D:\QuantOpsScheduler\state\shared-data\quantmarket-latest-status.json`
- 필요한 대시보드/요약:
  - task별 latest run status
  - last success time
  - stale 여부
  - failure reason
  - next run time
  - output manifest validation summary
- 다른 쓰레드가 읽을 표준 파일명:
  - `quantmarket-latest-status.json`
  - `quantmarket-market-analysis-current-status.json`
  - `quantmarket-intraday-current-status.json`
  - `quantmarket-market-environment-current-status.json`
  - `quantmarket-backup-current-status.json`
- 알림이 필요한 실패 유형:
  - task non-zero exit
  - 2회 이상 연속 실패
  - output stale
  - GCS publish fail
  - backup missing > 24h
- 알림이 불필요한 정상 스킵 조건:
  - 휴장일
  - 장중 작업이 장외 시간에 skip
  - `public_publish.lock`이 90분 미만이라 public refresh를 skip
  - 외부 API 공식 점검으로 retry 예약된 상태

## 7. 반복 자동실행 이관 제외 참고

아래 항목은 중요하지만 반복적으로 일정 시간에 계속 실행되는 자동작업이 아니므로 본문 이관 대상에서 제외합니다.

- Kiwoom API service recovery retry
  - Codex heartbeat `kiwoom`
  - 2026-05-23 18:05 KST 1회성 복구 확인 작업
  - 상시 반복 스케줄 아님
- Quant model market-context handoff refresh
  - Quant `data-refresh-only` 완료 후 요청 기반 수동/이벤트성 작업
  - 대표 검증 명령:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quant_model_handoff.py --expected-asof YYYY-MM-DD
```

  - 반복 시간 스케줄이 아니라 Quant 모델 run 전 종속 작업이므로, 허브에서는 별도 workflow dependency 또는 작업요청서 방식으로 관리 권장

## 8. 현재 조회된 반복 작업 상태 스냅샷

- `QuantMarket-Daily-Backup`
  - State: Ready
  - LastTaskResult: 0
  - NextRunTime: 2026-05-23 20:40:00
- `QuantMarket-Dev-Hourly`
  - State: Ready
  - LastTaskResult: 0
  - NextRunTime: 2026-05-23 12:05:00
- `QuantMarket-Dev-Intraday`
  - State: Ready
  - LastTaskResult: 0
  - NextRunTime: 2026-05-25 09:00:00
- `QuantMarket-Dev-US-Live`
  - State: Ready
  - LastTaskResult: 2147946720
  - NextRunTime: 2026-05-25 20:00:00
