from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _parse_date(value: object) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    # Socrata dates often look like 2026-06-09T00:00:00.000
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [kw for kw in keywords if kw.lower() in low]


def score_leads(df: pd.DataFrame, scoring_cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    scoring_cfg = scoring_cfg or {}
    high_value_keywords = scoring_cfg.get("high_value_keywords", [])
    bay_area_cities = scoring_cfg.get("bay_area_cities", [])
    now = datetime.now(timezone.utc)

    rows = []
    for _, row in df.iterrows():
        score = 0
        reasons: list[str] = []
        all_text = " ".join(str(row.get(c, "")) for c in df.columns).lower()
        category_text = f"{row.get('category','')} {row.get('raw_category','')}".lower()
        source = str(row.get("source", "")).lower()

        matched_keywords = _contains_any(all_text, high_value_keywords)
        if matched_keywords:
            score += 25
            reasons.append("high-trust/high-complaint category: " + ", ".join(matched_keywords[:3]))

        if "contractor" in source or str(row.get("license_number", "")).strip():
            score += 20
            reasons.append("licensed or license-linked business")

        if "permit" in source or str(row.get("permit_number", "")).strip():
            score += 20
            reasons.append("recent/current permit activity")

        if "chamber" in source or "association" in source:
            score += 15
            reasons.append("already pays for credibility/network affiliation")

        if str(row.get("website", "")).strip():
            score += 5
            reasons.append("has website")
        if str(row.get("phone", "")).strip():
            score += 5
            reasons.append("has phone")

        city = str(row.get("city", "")).lower()
        if city and any(c in city for c in bay_area_cities):
            score += 5
            reasons.append("Bay Area target geography")
        elif any(c in all_text for c in bay_area_cities):
            score += 3
            reasons.append("likely Bay Area geography")

        for date_col, label in (
            ("business_start_date", "new business/start date"),
            ("permit_date", "recent permit date"),
        ):
            dt = _parse_date(row.get(date_col, ""))
            if dt:
                days = (now - dt).days
                if 0 <= days <= 90:
                    score += 20
                    reasons.append(label + f" within 90 days ({days} days)")
                elif 90 < days <= 365:
                    score += 8
                    reasons.append(label + " within last year")
                break

        # BBB-friendly home services get an extra bump.
        if re.search(r"roof|solar|hvac|plumb|electri|remodel|restoration|moving|auto repair|smog", category_text + " " + all_text):
            score += 15
            reasons.append("BBB-sweet-spot vertical")

        row = row.to_dict()
        row["lead_score"] = score
        row["reason_to_call"] = "; ".join(dict.fromkeys(reasons))
        rows.append(row)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["lead_score", "business_name"], ascending=[False, True])
    return out
