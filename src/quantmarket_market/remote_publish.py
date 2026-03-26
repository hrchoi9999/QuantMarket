from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from .analytics import format_kst
from .config import (
    REMOTE_ACCESS_MODE,
    REMOTE_BASE_URL,
    REMOTE_CREDENTIALS_PATH,
    REMOTE_DRY_RUN,
    REMOTE_GCS_BUCKET,
    REMOTE_PREFIX,
    REMOTE_PUBLISH_ENABLED,
    REMOTE_PUBLISH_PROVIDER,
)

HANDOFF_FILENAMES = [
    "quantservice_market_home.json",
    "quantservice_market_today.json",
    "quantservice_market_page.json",
    "quantservice_market_timeline.json",
    "quantservice_market_asset_strength.json",
    "quantservice_market_state_transition.json",
    "quantservice_market_model_background.json",
    "quantservice_market_manifest.json",
    "api_v1_market_analysis_home.json",
    "api_v1_market_analysis_page.json",
    "api_v1_market_analysis_summary.json",
    "api_v1_market_analysis_detail.json",
    "api_v1_market_analysis_today_bridge.json",
    "api_v1_market_analysis_timeline.json",
    "api_v1_market_analysis_asset_strength.json",
    "api_v1_market_analysis_state_transition.json",
    "api_v1_market_analysis_model_background.json",
]
OAUTH_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"
GCS_UPLOAD_URL = "https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?{query}"


def _normalize_remote_updated(value: str | None) -> str | None:
    if not value:
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return format_kst(parsed.astimezone(timezone(timedelta(hours=9))))


class RemotePublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemotePublishConfig:
    enabled: bool = REMOTE_PUBLISH_ENABLED
    provider: str = REMOTE_PUBLISH_PROVIDER
    gcs_bucket: str = REMOTE_GCS_BUCKET
    base_url: str = REMOTE_BASE_URL
    prefix: str = REMOTE_PREFIX
    access_mode: str = REMOTE_ACCESS_MODE
    credentials_path: Path | None = REMOTE_CREDENTIALS_PATH
    dry_run: bool = REMOTE_DRY_RUN

    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        if self.provider == "gcs" and self.gcs_bucket:
            bucket = self.gcs_bucket.removeprefix("gs://")
            return f"https://storage.googleapis.com/{bucket}/{self.prefix}/current"
        raise RemotePublishError("Remote publish base URL is not configured.")

    def validate(self) -> None:
        if not self.enabled:
            return
        if self.provider != "gcs":
            raise RemotePublishError(f"Unsupported remote publish provider: {self.provider}")
        if not self.gcs_bucket:
            raise RemotePublishError("QUANTMARKET_REMOTE_GCS_BUCKET is required for GCS publish.")
        if self.credentials_path and not self.credentials_path.exists():
            raise RemotePublishError(
                f"Remote publish credentials file does not exist: {self.credentials_path}"
            )


class _GcsJsonPublisher:
    def __init__(self, config: RemotePublishConfig) -> None:
        self.config = config
        self.credentials = self._load_credentials(config)
        self._auth_request = GoogleAuthRequest()

    @staticmethod
    def _load_credentials(config: RemotePublishConfig):
        if config.credentials_path:
            return service_account.Credentials.from_service_account_file(
                str(config.credentials_path),
                scopes=[OAUTH_SCOPE],
            )
        credentials, _ = google.auth.default(scopes=[OAUTH_SCOPE])
        return credentials

    def _access_token(self) -> str:
        if not self.credentials.valid:
            self.credentials.refresh(self._auth_request)
        return self.credentials.token

    def upload_bytes(self, *, object_name: str, payload: bytes, content_type: str) -> dict:
        query = urlencode({"uploadType": "media", "name": object_name})
        bucket = quote(self.config.gcs_bucket.removeprefix("gs://"), safe="")
        url = GCS_UPLOAD_URL.format(bucket=bucket, query=query)
        request = Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": content_type,
                "Content-Length": str(len(payload)),
            },
        )
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8-sig"))


def _load_handoff_payloads(handoff_dir: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for filename in HANDOFF_FILENAMES:
        path = handoff_dir / filename
        if not path.exists():
            raise RemotePublishError(f"Missing handoff file for remote publish: {path}")
        payloads[filename] = path.read_bytes()
    return payloads


def publish_remote_handoff(
    *,
    handoff_dir: Path,
    run_id: str,
    asof: str,
    config: RemotePublishConfig | None = None,
) -> dict:
    config = config or RemotePublishConfig()
    if not config.enabled:
        return {
            "enabled": False,
            "provider": config.provider,
        }

    config.validate()
    payloads = _load_handoff_payloads(handoff_dir)
    asof_date = asof[:10]
    current_base_url = config.resolved_base_url()
    history_prefix = f"{config.prefix}/history/{asof_date}/{run_id}"
    current_prefix = f"{config.prefix}/current"
    ordered_current_files = [
        filename for filename in HANDOFF_FILENAMES if filename != "quantservice_market_manifest.json"
    ] + ["quantservice_market_manifest.json"]

    if config.dry_run:
        return {
            "enabled": True,
            "provider": config.provider,
            "dry_run": True,
            "access_mode": config.access_mode,
            "base_url": current_base_url,
            "history_prefix": history_prefix,
            "current_prefix": current_prefix,
            "run_id": run_id,
            "files": {
                filename: f"{current_base_url}/{filename}" for filename in HANDOFF_FILENAMES
            },
            "fallback_policy": "QuantService remote failure -> local fallback",
            "update_interval_minutes": 60,
        }

    publisher = _GcsJsonPublisher(config)
    history_results: dict[str, dict] = {}
    current_results: dict[str, dict] = {}

    for filename, payload in payloads.items():
        object_name = f"{history_prefix}/{filename}"
        history_results[filename] = publisher.upload_bytes(
            object_name=object_name,
            payload=payload,
            content_type=mimetypes.guess_type(filename)[0] or "application/json; charset=utf-8",
        )

    for filename in ordered_current_files:
        payload = payloads[filename]
        object_name = f"{current_prefix}/{filename}"
        current_results[filename] = publisher.upload_bytes(
            object_name=object_name,
            payload=payload,
            content_type=mimetypes.guess_type(filename)[0] or "application/json; charset=utf-8",
        )

    return {
        "enabled": True,
        "provider": config.provider,
        "dry_run": False,
        "access_mode": config.access_mode,
        "base_url": current_base_url,
        "history_prefix": history_prefix,
        "current_prefix": current_prefix,
        "run_id": run_id,
        "files": {
            filename: f"{current_base_url}/{filename}" for filename in HANDOFF_FILENAMES
        },
        "current_object_meta": {
            filename: {
                "etag": current_results[filename].get("etag"),
                "updated": _normalize_remote_updated(current_results[filename].get("updated")),
                "generation": current_results[filename].get("generation"),
            }
            for filename in current_results
        },
        "fallback_policy": "QuantService remote failure -> local fallback",
        "update_interval_minutes": 60,
    }
