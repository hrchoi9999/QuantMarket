# QuantMarket Remote Handoff Publish Guide (2026-03-24)

## 목적
QuantMarket가 생성한 시장분석 handoff JSON을 QuantService Cloud Run이 URL로 읽을 수 있도록
`market_analysis/current/` 구조로 원격 publish 한다.

## 현재 운영값
- GCS 버킷명: `quantservice-489808-market-analysis`
- GCS 업로드 경로: `gs://quantservice-489808-market-analysis/market_analysis/current/`
- 공개 base URL: `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`
- 업로드용 서비스 계정: `quantmarket-handoff@quantservice-489808.iam.gserviceaccount.com`
- 서비스계정 JSON 키 경로: `D:\QuantService\data\gcp\quantmarket-handoff-uploader.json`
- 접근 방식: `public`
- 갱신 주기: `60분`
- 실패 시 fallback: `QuantService remote failure -> local fallback`

## 유지되는 파일명
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`
- `api_v1_market_analysis_home.json`
- `api_v1_market_analysis_page.json`
- `api_v1_market_analysis_summary.json`
- `api_v1_market_analysis_detail.json`
- `api_v1_market_analysis_today_bridge.json`

## publish 동작 방식
1. QuantMarket가 로컬 handoff JSON 세트를 생성한다.
2. 동일 파일셋을 history prefix에 먼저 업로드한다.
3. 그 다음 current prefix를 덮어쓴다.
4. `quantservice_market_manifest.json`은 current 단계에서 마지막에 업로드한다.
5. publish 결과는 `reports/market_analysis/remote_publish_status_latest.json`에 남긴다.

## 원자성/일관성 메모
GCS 정적 객체는 디렉터리 전체를 완전 원자적으로 교체할 수는 없다.
대신 아래 방식으로 partial mismatch를 최소화한다.
- history 세트를 먼저 완성
- current 세트를 payload 먼저 업로드
- manifest를 마지막에 업로드
- 각 객체 overwrite 시 GCS의 `updated`, `etag`, `generation`이 갱신됨

## 실행 방법
전체 파이프라인 + 원격 publish:
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_market_analysis_pipeline.py --market KR --asof 2026-03-24T11:00:00+09:00 --publish-remote --remote-gcs-bucket quantservice-489808-market-analysis --remote-base-url https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current --remote-access-mode public --remote-credentials D:\QuantService\data\gcp\quantmarket-handoff-uploader.json
```

원격 publish dry-run:
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_market_analysis_pipeline.py --market KR --asof 2026-03-24T11:00:00+09:00 --skip-official-collect --publish-remote --remote-dry-run --remote-gcs-bucket quantservice-489808-market-analysis
```

기존 handoff만 별도 재전송:
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\publish_market_analysis_remote.py --asof 2026-03-24T11:00:00+09:00 --remote-gcs-bucket quantservice-489808-market-analysis --remote-base-url https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current --remote-access-mode public --remote-credentials D:\QuantService\data\gcp\quantmarket-handoff-uploader.json
```

## 현재 검증 상태
- 실업로드 성공
- 공개 manifest URL 응답 확인 성공
- UTF-8 한글 payload 정상 확인
- `ETag`, `updated`, `generation` 갱신 확인

운영 manifest URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current/quantservice_market_manifest.json`

## QuantService 전달 정보
1. 공용 base URL
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

2. 접근 방식
- `public`

3. 실제 갱신 주기
- `60분`

4. 실패 시 fallback 정책
- `QuantService remote failure -> local fallback`

5. 운영 기준 manifest 샘플
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\quantservice_market_manifest.json`

## 현재 산출물
- 로컬 handoff: `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current`
- publish 리포트: `D:\QuantMarket\reports\market_analysis\remote_publish_status_latest.json`
