# QuantMarket Secret Handling Note (2026-03-24)

## 현재 상태
- 실제 `OPENAI_API_KEY` 와 `GEMINI_API_KEY` 값은 코드 파일에 저장하지 않았다.
- 두 키는 사용자 환경변수로만 설정되어 있다.
- 코드에서는 환경변수 이름만 참조한다.

참조 위치:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`

## 주의사항
- 실제 키 문자열을 Python 파일, PowerShell 스크립트, 문서, JSON 산출물에 넣지 않는다.
- 키가 필요한 경우 로컬 개발은 환경변수로만 주입한다.
- 운영 전환 시에는 Secret Manager 또는 Cloud Run 환경변수로 주입한다.
- 로그/리포트에 키 자체를 남기지 않는다.

## git 방지
- `.gitignore`에 `.env`, `data/gcp/`, 로컬 시크릿 파일 패턴을 추가했다.
- 현재 작업공간은 git 저장소가 아니지만, 이후 저장소로 초기화되더라도 기본적인 시크릿 패턴은 추적 제외된다.

## 권장 운영 방식
- 로컬: 사용자 환경변수
- 클라우드: Secret Manager 또는 배포 환경변수
- 코드/문서/JSON 산출물: 키 저장 금지
