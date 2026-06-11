from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from bbb_lead_scraper.http import HttpClient, socrata_headers

log = logging.getLogger(__name__)


class SocrataSource:
    """Pull from a Socrata SODA API endpoint in pages."""

    def __init__(self, name: str, cfg: dict[str, Any]):
        self.name = name
        self.cfg = cfg
        self.domain = cfg["domain"].rstrip("/")
        self.dataset_id = cfg["dataset_id"]
        self.limit = int(cfg.get("limit", 50000))
        self.page_size = min(int(cfg.get("page_size", 5000)), 50000)
        self.client = HttpClient(headers=socrata_headers())

    @property
    def endpoint(self) -> str:
        return f"https://{self.domain}/resource/{self.dataset_id}.json"

    def _metadata_url(self) -> str:
        return f"https://{self.domain}/api/views/{self.dataset_id}"

    def available_columns(self) -> set[str]:
        try:
            resp = self.client.get(self._metadata_url())
            meta = resp.json()
            cols = {c.get("fieldName", "") for c in meta.get("columns", [])}
            return {c for c in cols if c}
        except Exception as exc:  # noqa: BLE001 - metadata can fail without blocking the scraper
            log.warning("Could not fetch Socrata metadata for %s: %s", self.name, exc)
            return set()

    def _build_where(self, days_back: int | None = None) -> str | None:
        clauses: list[str] = []
        columns = self.available_columns()
        if days_back:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).date().isoformat()
            for candidate in self.cfg.get("recency_date_candidates", []):
                if not columns or candidate in columns:
                    clauses.append(f"{candidate} >= '{cutoff}'")
                    break
        extra = self.cfg.get("where_extra")
        if extra:
            # Only add if all obvious identifiers in the expression are present or metadata is unavailable.
            if not columns:
                clauses.append(extra)
            else:
                identifiers = [tok for tok in extra.replace("(", " ").replace(")", " ").replace("'", " ").split() if tok.isidentifier()]
                if all(tok.lower() in {c.lower() for c in columns} or tok.upper() in {"IS", "NULL", "OR", "AND", "NOT", "LIKE", "UPPER"} for tok in identifiers):
                    clauses.append(extra)
        if not clauses:
            return None
        return " AND ".join(f"({c})" for c in clauses)

    def fetch(self, days_back: int | None = None) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        offset = 0
        where = self._build_where(days_back)
        while offset < self.limit:
            params: dict[str, Any] = {"$limit": self.page_size, "$offset": offset}
            if where:
                params["$where"] = where
            try:
                resp = self.client.get(self.endpoint, params=params)
            except requests.HTTPError as exc:
                if where:
                    log.warning("Filtered query failed for %s; retrying unfiltered. Error: %s", self.name, exc)
                    where = None
                    offset = 0
                    rows = []
                    continue
                raise
            page = resp.json()
            if not page:
                break
            rows.extend(page)
            if len(page) < self.page_size:
                break
            offset += self.page_size
        df = pd.DataFrame(rows)
        if df.empty:
            log.warning("No rows returned for %s", self.name)
        return df
