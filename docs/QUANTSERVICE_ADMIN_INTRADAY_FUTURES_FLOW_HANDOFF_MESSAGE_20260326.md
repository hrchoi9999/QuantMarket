QS 전달 메시지

QuantMarket 쪽에서 admin 전용 장중 intraday payload에 `선물/수급` 보조지표를 추가 반영했습니다.

이번에 추가된 항목:
- 선물: `FUT`
- 수급: `PROGRAM_TOTAL_NET`, `PROGRAM_NONARB_NET`, `FOREIGNER_NET`, `INSTITUTION_NET`
- overlay: `signal_overlay.futures_overlay`, `signal_overlay.flow_overlay`

최신 admin current 기준 확인 완료:
- `admin_market_intraday_summary.json`
- `admin_market_intraday_detail.json`
- 기준시각: `2026-03-26T15:42:52+09:00`
- session_status: `live`

현재 확인된 예시 값:
- FUT: `809.10`, `-3.84%`
- 프로그램 전체 순매수: `-16,251억원`
- 외국인 순매수: `-30,980억원`

QS 쪽에서는 이 데이터를 public이 아닌 `/admin` 전용 시장 브리핑 Lab에만 연결해 주세요.
공개 페이지 반영은 아직 하지 않습니다.

붙여넣기용 작업지시문:
- `D:\QuantMarket\docs\QUANTSERVICE_ADMIN_INTRADAY_FUTURES_FLOW_TASK_PROMPT_20260326.md`
