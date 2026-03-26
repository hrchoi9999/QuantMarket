이번 작업은 `D:\QuantService`에서 진행합니다.

작업 목적:
- QuantMarket이 생성하는 admin 전용 시장 브리핑 추가 정보 payload를 `redbot.co.kr/admin` 하위 페이지에서만 노출합니다.
- 이 기능은 공개 페이지에 반영하지 않고, 로그인된 관리자 계정에서만 접근 가능하게 구현합니다.
- 사용자 최종 승인 전까지는 public 메뉴/공개 route/공개 링크에 연결하지 않습니다.

중요 원칙:
1. 이번 기능은 `admin_only_pre_publish` 단계입니다.
2. 공개 `시장 브리핑` 페이지와 섞지 말고, `/admin` 하위 전용 화면으로 구성합니다.
3. 상단 공개 메뉴에는 노출하지 않습니다.
4. QuantMarket은 생산자이고 QuantService는 admin UI 소비 계층입니다.

QuantMarket admin payload 파일셋:
- `admin_market_timeline.json`
- `admin_market_asset_strength.json`
- `admin_market_state_transition.json`
- `admin_market_model_background.json`
- `admin_market_manifest.json`

개발단계 handoff 참고 경로:
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantservicedmin_market\current`

파일 의미:
1. `admin_market_timeline.json`
- 최근 시장상태와 total_score / component score 흐름
- 최근 시점별 상태 변화 타임라인

2. `admin_market_asset_strength.json`
- 자산군 상대강도 current ranking
- 자산군 rank history
- 자산군: KOSPI / KOSDAQ / USDKRW / BOND / GOLD / INVERSE

3. `admin_market_state_transition.json`
- 현재 상태 지속시간
- 최근 5일/20일 상태 전이 횟수
- 안정도 점수
- 최근 상태 변화 목록

4. `admin_market_model_background.json`
- 모델 해석 백그라운드 요약
- favorable / caution signals
- top assets / bottom assets
- 현재 상태와 브리핑 톤 연결

5. `admin_market_manifest.json`
- admin 전용 파일셋 manifest
- `visibility=admin_only_pre_publish`

추천 admin 페이지 구성:

### 1. `/admin/market-briefing-lab`
메인 admin 실험 페이지

권장 섹션 순서:
1. 현재 시장상태 요약
2. 모델 해석 백그라운드
3. 상태 타임라인
4. 자산군 상대강도
5. 상태 전이 브리핑
6. raw data 다운로드/확인 링크

### 2. 상태 타임라인 카드
사용 파일:
- `admin_market_timeline.json`

표시 권장:
- 현재 상태 라벨
- 현재 total_score
- 최근 1주 상태 변화 차트
- trend / breadth / risk / defensive 흐름 미니차트
- 최근 강해짐/약해짐 여부

### 3. 자산군 상대강도 카드
사용 파일:
- `admin_market_asset_strength.json`

표시 권장:
- 현재 rank 1~6 표
- 강함/중립/약함 배지
- 최근 rank 변화
- 자산군별 ret_20d / strength_score

### 4. 상태 전이 카드
사용 파일:
- `admin_market_state_transition.json`

표시 권장:
- 현재 상태 지속시간
- 최근 5일 전이 횟수
- 최근 20일 전이 횟수
- stability_score
- 최근 변화 로그

### 5. 모델 해석 백그라운드 카드
사용 파일:
- `admin_market_model_background.json`

표시 권장:
- summary_line
- reference_note
- briefing_tone
- favorable_signals
- caution_signals
- top_assets / bottom_assets

접근 제어:
- 반드시 로그인 후 관리자 계정만 접근 가능
- 공개 네비게이션 미노출
- sitemap / 공개 링크 미포함
- robots 노출 제외 가능하면 적용

금지사항:
- public `/market-briefing`에 이 데이터 연결
- 공개 홈에 링크 노출
- 비로그인 접근 허용
- 아직 승인 전인데 운영 public source를 읽도록 연결

권장 구현 방식:
- QuantService 내부 admin loader 추가
- 로컬 파일 또는 별도 admin source를 읽도록 구현
- public market source loader와 분리
- 에러 시 `admin data unavailable` 정도의 내부 fallback 제공

QA 체크리스트:
- [ ] `/admin` 하위에서만 접근 가능한가?
- [ ] 공개 메뉴에서 보이지 않는가?
- [ ] timeline / asset strength / state transition / model background 4개 섹션이 모두 보이는가?
- [ ] 비로그인 사용자에게 노출되지 않는가?
- [ ] 승인 전 public 시장 브리핑 페이지에는 반영되지 않는가?
