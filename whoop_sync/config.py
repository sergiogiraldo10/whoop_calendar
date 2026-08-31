import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # no-op in CI where there's no .env file — real env vars there come from GitHub Actions secrets


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


@dataclass
class JobConfig:
    whoop_client_id: str
    whoop_client_secret: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    cf_account_id: str
    cf_api_token: str
    cf_namespace_id: str
    calendar_id: str
    to_email: Optional[str]
    to_sms_gateway: Optional[str]


def load_job_config() -> JobConfig:
    return JobConfig(
        whoop_client_id=_required("WHOOP_CLIENT_ID"),
        whoop_client_secret=_required("WHOOP_CLIENT_SECRET"),
        google_client_id=_required("GOOGLE_CLIENT_ID"),
        google_client_secret=_required("GOOGLE_CLIENT_SECRET"),
        google_refresh_token=_required("GOOGLE_REFRESH_TOKEN"),
        cf_account_id=_required("CF_ACCOUNT_ID"),
        cf_api_token=_required("CF_API_TOKEN"),
        cf_namespace_id=_required("CF_KV_NAMESPACE_ID"),
        calendar_id=os.environ.get("CALENDAR_ID", "primary"),
        to_email=os.environ.get("TO_EMAIL"),
        to_sms_gateway=os.environ.get("TO_SMS_GATEWAY"),
    )
