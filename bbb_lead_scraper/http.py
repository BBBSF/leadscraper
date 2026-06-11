from __future__ import annotations

import os
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

DEFAULT_HEADERS = {
    "User-Agent": "BBBLeadEngine/0.1 (+public-data-lead-collection; respectful rate limits)",
    "Accept": "text/html,application/json,text/csv;q=0.9,*/*;q=0.8",
}


class HttpClient:
    def __init__(self, timeout: int = 45, headers: dict[str, str] | None = None):
        self.session = requests.Session()
        self.timeout = timeout
        merged = dict(DEFAULT_HEADERS)
        if headers:
            merged.update(headers)
        self.session.headers.update(merged)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(4))
    def get(self, url: str, **kwargs: Any) -> requests.Response:
        resp = self.session.get(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp


def socrata_headers() -> dict[str, str]:
    token = os.getenv("SOCRATA_APP_TOKEN", "").strip()
    return {"X-App-Token": token} if token else {}
