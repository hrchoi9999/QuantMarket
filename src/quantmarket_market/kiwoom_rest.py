from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

KIWOOM_HOST = "https://api.kiwoom.com"
TOKEN_ENDPOINT = "/oauth2/token"

DEFAULT_APPKEY_FILE = Path(r"D:\Quant\config\kiwoom_54810245_appkey.txt")
DEFAULT_SECRETKEY_FILE = Path(r"D:\Quant\config\kiwoom_54810245_secretkey.txt")

# Kiwoom REST public guide currently exposes domestic stock/ETF REST TRs.
# Keep the futures request configurable so we can switch to the official TR
# as soon as Kiwoom confirms the Korea night-futures REST endpoint/api-id.
DEFAULT_KOREA_FUTURES_ENDPOINT = os.getenv("QUANTMARKET_KIWOOM_KOREA_FUTURES_ENDPOINT", "/api/dostk/stkinfo")
DEFAULT_KOREA_FUTURES_API_ID = os.getenv("QUANTMARKET_KIWOOM_KOREA_FUTURES_API_ID", "ka10001")
DEFAULT_KOREA_FUTURES_BODY = os.getenv(
    "QUANTMARKET_KIWOOM_KOREA_FUTURES_BODY",
    json.dumps({"stk_cd": "A0166000"}, ensure_ascii=False),
)


def _read_secret(path: Path) -> str:
    value = path.read_text(encoding="utf-8-sig").strip()
    if not value:
        raise RuntimeError(f"empty Kiwoom key file: {path}")
    return value


def _post_json(url: str, *, headers: dict[str, str], body: dict[str, Any], timeout: int = 30) -> tuple[dict[str, Any], dict[str, str]]:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return parsed, dict(response.headers.items())
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Kiwoom HTTP {exc.code}: {body_text[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Kiwoom network error: {exc}") from exc


def get_access_token(
    *,
    appkey_file: Path = DEFAULT_APPKEY_FILE,
    secretkey_file: Path = DEFAULT_SECRETKEY_FILE,
    host: str = KIWOOM_HOST,
) -> tuple[str, str | None]:
    appkey = _read_secret(appkey_file)
    secretkey = _read_secret(secretkey_file)
    payload, _headers = _post_json(
        f"{host}{TOKEN_ENDPOINT}",
        headers={"Content-Type": "application/json;charset=UTF-8"},
        body={"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
        timeout=60,
    )
    if int(payload.get("return_code", -1)) != 0 or not payload.get("token"):
        raise RuntimeError(
            f"Kiwoom token failed: return_code={payload.get('return_code')}, return_msg={payload.get('return_msg')}"
        )
    return str(payload["token"]), payload.get("expires_dt")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "-", "None", "nan"}:
        return None
    sign = -1.0 if text.startswith("-") else 1.0
    text = text.lstrip("+-")
    try:
        return sign * float(text)
    except ValueError:
        return None


def _recursive_find(payload: Any, keys: list[str]) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return payload[key]
        for value in payload.values():
            found = _recursive_find(value, keys)
            if found is not None:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _recursive_find(item, keys)
            if found is not None:
                return found
    return None


def _parse_change_pct(payload: dict[str, Any], price: float | None, prev_close: float | None) -> float | None:
    pct_value = _safe_float(
        _recursive_find(
            payload,
            [
                "flu_rt",
                "fluctuation_rate",
                "change_rate",
                "chg_rt",
                "등락률",
                "전일대비율",
            ],
        )
    )
    if pct_value is not None:
        return pct_value / 100.0 if abs(pct_value) > 1 else pct_value
    if price is not None and prev_close not in (None, 0):
        return price / prev_close - 1.0
    return None


def request_korea_night_futures_quote(
    *,
    token: str,
    endpoint: str = DEFAULT_KOREA_FUTURES_ENDPOINT,
    api_id: str = DEFAULT_KOREA_FUTURES_API_ID,
    request_body: dict[str, Any] | None = None,
    host: str = KIWOOM_HOST,
) -> dict[str, Any]:
    body = request_body
    if body is None:
        body = json.loads(DEFAULT_KOREA_FUTURES_BODY)
    payload, headers = _post_json(
        f"{host}{endpoint}",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
            "cont-yn": "N",
            "next-key": "",
        },
        body=body,
        timeout=60,
    )
    if int(payload.get("return_code", 0)) != 0:
        raise RuntimeError(
            f"Kiwoom {api_id} failed: return_code={payload.get('return_code')}, return_msg={payload.get('return_msg')}"
        )

    price = _safe_float(
        _recursive_find(payload, ["cur_prc", "now_prc", "stck_prpr", "price", "현재가", "TDD_CLSPRC"])
    )
    prev_close = _safe_float(
        _recursive_find(payload, ["base_pric", "pred_close", "prev_close", "전일종가", "SETL_PRC"])
    )
    change_value = _safe_float(
        _recursive_find(payload, ["pred_pre", "change_value", "prdy_vrss", "대비", "CMPPREVDD_PRC"])
    )
    if change_value is None and price is not None and prev_close not in (None, 0):
        change_value = price - prev_close
    change_pct = _parse_change_pct(payload, price, prev_close)

    return {
        "price": price,
        "prev_close": prev_close,
        "change_value": change_value,
        "change_pct": change_pct,
        "open": _safe_float(_recursive_find(payload, ["open_pric", "open", "시가", "TDD_OPNPRC"])),
        "high": _safe_float(_recursive_find(payload, ["high_pric", "high", "고가", "TDD_HGPRC"])),
        "low": _safe_float(_recursive_find(payload, ["low_pric", "low", "저가", "TDD_LWPRC"])),
        "volume": _safe_float(_recursive_find(payload, ["trde_qty", "volume", "거래량", "ACC_TRDVOL"])),
        "source": f"kiwoom_rest:{api_id}:{endpoint}",
        "request_body": body,
        "response_header": headers,
        "raw_payload": payload,
    }


def collect_korea_night_futures_proxy() -> dict[str, Any]:
    token, expires_dt = get_access_token()
    quote = request_korea_night_futures_quote(token=token)
    quote["token_expires_dt"] = expires_dt
    return quote
