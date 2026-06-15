from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from bbb_lead_scraper.normalize import clean_text, normalize_phone

log = logging.getLogger(__name__)

FIND_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


@dataclass
class PlaceMatch:
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    place_id: str = ""
    confidence: int = 0
    status: str = ""


def _tokens(value: str) -> set[str]:
    stop = {"inc", "llc", "co", "corp", "corporation", "company", "the", "and", "of"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1 and token not in stop
    }


def match_confidence(row: pd.Series, place: dict[str, Any]) -> int:
    source_name = clean_text(row.get("business_name", ""))
    place_name = clean_text(place.get("name", ""))
    source_tokens = _tokens(source_name)
    place_tokens = _tokens(place_name)

    score = 0
    if source_tokens and place_tokens:
        overlap = len(source_tokens & place_tokens)
        score += round(70 * overlap / max(len(source_tokens), len(place_tokens)))

    source_city = clean_text(row.get("city", "")).lower()
    source_zip = clean_text(row.get("zip", ""))
    place_address = clean_text(place.get("formatted_address", "")).lower()
    if source_city and source_city in place_address:
        score += 15
    if source_zip and source_zip in place_address:
        score += 15

    return min(score, 100)


def build_query(row: pd.Series) -> str:
    parts = [
        clean_text(row.get("business_name", "")),
        clean_text(row.get("address", "")),
        clean_text(row.get("city", "")),
        clean_text(row.get("state", "")),
        clean_text(row.get("zip", "")),
    ]
    return " ".join(part for part in parts if part)


class GooglePlacesClient:
    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY", "")
        self.timeout = timeout
        self.session = requests.Session()
        if not self.api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY is not set")

    def find_place(self, query: str) -> dict[str, Any] | None:
        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address,business_status",
            "key": self.api_key,
        }
        data = self.session.get(FIND_URL, params=params, timeout=self.timeout).json()
        status = data.get("status", "")
        if status != "OK":
            log.debug("Google Places find status for %s: %s %s", query, status, data.get("error_message", ""))
            return None
        candidates = data.get("candidates") or []
        return candidates[0] if candidates else None

    def place_details(self, place_id: str) -> dict[str, Any]:
        params = {
            "place_id": place_id,
            "fields": "name,formatted_phone_number,international_phone_number,website,url,formatted_address",
            "key": self.api_key,
        }
        data = self.session.get(DETAILS_URL, params=params, timeout=self.timeout).json()
        if data.get("status") != "OK":
            log.debug("Google Places details status for %s: %s", place_id, data.get("status"))
            return {}
        return data.get("result", {})

    def enrich_row(self, row: pd.Series, min_confidence: int = 70) -> PlaceMatch:
        query = build_query(row)
        if not query or not clean_text(row.get("business_name", "")):
            return PlaceMatch(status="skipped_no_query")

        candidate = self.find_place(query)
        if not candidate or not candidate.get("place_id"):
            return PlaceMatch(status="not_found")

        confidence = match_confidence(row, candidate)
        if confidence < min_confidence:
            return PlaceMatch(
                name=clean_text(candidate.get("name", "")),
                address=clean_text(candidate.get("formatted_address", "")),
                place_id=clean_text(candidate.get("place_id", "")),
                confidence=confidence,
                status="low_confidence",
            )

        details = self.place_details(candidate["place_id"])
        return PlaceMatch(
            name=clean_text(details.get("name") or candidate.get("name", "")),
            phone=normalize_phone(details.get("formatted_phone_number") or details.get("international_phone_number") or ""),
            website=clean_text(details.get("website", "")),
            address=clean_text(details.get("formatted_address") or candidate.get("formatted_address", "")),
            place_id=clean_text(candidate.get("place_id", "")),
            confidence=confidence,
            status="matched",
        )


def enrich_dataframe(
    df: pd.DataFrame,
    *,
    limit: int = 25,
    min_confidence: int = 70,
    only_missing_phone: bool = True,
) -> pd.DataFrame:
    client = GooglePlacesClient()
    out = df.copy()
    for column in ("phone", "website"):
        if column in out.columns:
            out[column] = out[column].fillna("").astype("object")
    for column in (
        "google_place_name",
        "google_phone",
        "google_website",
        "google_address",
        "google_place_id",
        "google_enrichment_status",
    ):
        if column not in out.columns:
            out[column] = ""
    if "google_match_confidence" not in out.columns:
        out["google_match_confidence"] = 0

    eligible = out.index
    if only_missing_phone and "phone" in out.columns:
        eligible = out[out["phone"].fillna("").astype(str).str.strip().eq("")].index
    eligible = list(eligible[:limit])

    for count, idx in enumerate(eligible, start=1):
        row = out.loc[idx]
        match = client.enrich_row(row, min_confidence=min_confidence)
        out.at[idx, "google_place_name"] = match.name
        out.at[idx, "google_phone"] = match.phone
        out.at[idx, "google_website"] = match.website
        out.at[idx, "google_address"] = match.address
        out.at[idx, "google_place_id"] = match.place_id
        out.at[idx, "google_match_confidence"] = match.confidence
        out.at[idx, "google_enrichment_status"] = match.status
        if match.phone and not clean_text(row.get("phone", "")):
            out.at[idx, "phone"] = match.phone
        if match.website and not clean_text(row.get("website", "")):
            out.at[idx, "website"] = match.website
        log.info("Google Places enriched %d/%d: %s", count, len(eligible), match.status)

    return out
