from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

STANDARD_COLUMNS = [
    "business_name",
    "legal_name",
    "contact_name",
    "category",
    "source",
    "source_url",
    "record_url",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "website",
    "email",
    "license_number",
    "license_status",
    "permit_number",
    "permit_date",
    "permit_value",
    "business_start_date",
    "date_scraped",
    "lead_score",
    "reason_to_call",
    "raw_category",
]

CANDIDATES: dict[str, list[str]] = {
    "business_name": [
        "business_name", "dba_name", "dba", "company", "company_name", "name", "member_name",
        "business", "organization", "applicant", "contractor_name", "firm_name", "ownership_name",
    ],
    "legal_name": ["legal_name", "ownership_name", "owner_name", "licensee_name"],
    "contact_name": ["contact_name", "first_name", "last_name", "agent_name", "project_contact"],
    "raw_category": ["naics_code_description", "naics_description", "naics", "category", "categories", "classification", "classifications", "tax_code", "business_type"],
    "address": ["address", "location_address", "business_address", "street_address", "full_address", "mailing_address"],
    "city": ["city", "business_city", "location_city"],
    "state": ["state", "business_state", "location_state"],
    "zip": ["zip", "zipcode", "zip_code", "business_zip", "location_zip", "postal_code"],
    "phone": ["phone", "telephone", "phone_number", "business_phone", "tel"],
    "website": ["website", "web_site", "url", "business_website"],
    "email": ["email", "email_address"],
    "license_number": ["license_number", "license_no", "contractor_license", "lic_no", "license"],
    "license_status": ["license_status", "status", "business_status", "current_status"],
    "permit_number": ["permit_number", "permit_no", "application_number", "application_no", "record_id"],
    "permit_date": ["permit_creation_date", "filed_date", "issued_date", "completed_date", "permit_date"],
    "permit_value": ["estimated_cost", "revised_cost", "valuation", "permit_value", "job_value"],
    "business_start_date": ["business_start_date", "location_start_date", "dba_start_date", "issue_date", "start_date"],
    "record_url": ["record_url", "profile_url", "url"],
}

PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
ZIP_RE = re.compile(r"\b(9\d{4})(?:-\d{4})?\b")


def clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_phone(value: object) -> str:
    text = clean_text(value)
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return text


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(text or "")
    return normalize_phone(match.group(0)) if match else ""


def extract_zip(text: str) -> str:
    match = ZIP_RE.search(text or "")
    return match.group(1) if match else ""


def pick_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    lower_to_actual = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_to_actual:
            return lower_to_actual[c.lower()]
    # Conservative fallback: word-boundary matches only, so "street_name" does not become
    # a business name and geometry "location" does not become city/state.
    for c in candidates:
        wanted = c.lower()
        for actual_lower, actual in lower_to_actual.items():
            parts = set(actual_lower.replace("-", "_").split("_"))
            if wanted in parts:
                return actual
    return None


def _series_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    return df[column].map(clean_text)


def _join_columns(df: pd.DataFrame, columns: list[str], sep: str = " ") -> pd.Series:
    values = [_series_text(df, column) for column in columns]
    if not values:
        return pd.Series("", index=df.index, dtype="string")
    combined = values[0]
    for value in values[1:]:
        combined = combined.str.cat(value, sep=sep)
    return combined.map(clean_text)


def _apply_source_overrides(out: pd.DataFrame, df: pd.DataFrame, source_name: str) -> None:
    if source_name == "sf_building_permits":
        out["business_name"] = ""
        out["contact_name"] = ""
        out["address"] = _join_columns(
            df,
            ["street_number", "street_number_suffix", "street_name", "street_suffix", "unit", "unit_suffix"],
        )
        out["city"] = "San Francisco"
        out["state"] = "CA"
        out["zip"] = _series_text(df, "zipcode").str.extract(r"(\d{5})", expand=False).fillna("")
        out["phone"] = ""
        out["website"] = ""
        out["email"] = ""
        out["raw_category"] = _series_text(df, "description")
        out["permit_number"] = _series_text(df, "permit_number")
        out["permit_date"] = _series_text(df, "permit_creation_date")
        out["permit_value"] = _series_text(df, "estimated_cost")
        out["license_status"] = _series_text(df, "status")

    if source_name == "sf_building_permit_contacts":
        first = _series_text(df, "first_name")
        last = _series_text(df, "last_name")
        out["contact_name"] = first.str.cat(last, sep=" ").map(clean_text)
        out["business_name"] = _series_text(df, "firm_name")
        owner_mask = out["business_name"].str.lower().isin(["", "owner", "nan"])
        out.loc[owner_mask, "business_name"] = out.loc[owner_mask, "contact_name"]
        out["address"] = _series_text(df, "firm_address")
        out["city"] = _series_text(df, "firm_city")
        out["state"] = _series_text(df, "firm_state")
        out["zip"] = _series_text(df, "firm_zipcode").str.extract(r"(\d{5})", expand=False).fillna("")
        out["raw_category"] = _series_text(df, "role")
        out["permit_number"] = _series_text(df, "permit_number")
        out["license_number"] = _series_text(df, "license1")
        out["business_start_date"] = _series_text(df, "from_date")


def normalize_dataframe(df: pd.DataFrame, source_name: str, source_url: str, category: str = "") -> pd.DataFrame:
    """Normalize an arbitrary source dataframe into CRM-friendly lead columns."""
    out = pd.DataFrame(index=df.index)
    picked_columns: dict[str, str | None] = {}
    for col, candidates in CANDIDATES.items():
        picked = pick_column(df, candidates)
        picked_columns[col] = picked
        out[col] = df[picked] if picked else ""

    _apply_source_overrides(out, df, source_name)

    out["business_name"] = out["business_name"].map(clean_text)
    out["legal_name"] = out["legal_name"].map(clean_text)
    out["contact_name"] = out["contact_name"].map(clean_text)
    out["raw_category"] = out["raw_category"].map(clean_text)
    out["category"] = category or out["raw_category"]
    out["source"] = source_name
    out["source_url"] = source_url
    out["date_scraped"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out["phone"] = out["phone"].map(normalize_phone)
    out["zip"] = out["zip"].map(clean_text).str.extract(r"(\d{5})", expand=False).fillna("")

    # Fill missing city/zip/phone from address or raw concatenated row text when possible.
    raw_text = df.apply(lambda row: " | ".join(clean_text(value) for value in row), axis=1)
    if picked_columns.get("phone"):
        out["phone"] = out.apply(
            lambda r: r["phone"] or extract_phone(raw_text.loc[r.name]), axis=1
        )
    out["zip"] = out.apply(lambda r: r["zip"] or extract_zip(raw_text.loc[r.name]), axis=1)

    for col in STANDARD_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[STANDARD_COLUMNS]


def make_dedupe_key(row: pd.Series) -> str:
    name = clean_text(row.get("business_name", "")).lower()
    phone = re.sub(r"\D", "", clean_text(row.get("phone", "")))
    zip_code = clean_text(row.get("zip", ""))
    address = re.sub(r"[^a-z0-9]", "", clean_text(row.get("address", "")).lower())[:20]
    return "|".join([re.sub(r"[^a-z0-9]", "", name)[:40], phone, zip_code, address])


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    working = df.copy()
    working["_dedupe_key"] = working.apply(make_dedupe_key, axis=1)
    working = working.sort_values(["lead_score", "business_name"], ascending=[False, True])
    working = working.drop_duplicates("_dedupe_key", keep="first")
    return working.drop(columns=["_dedupe_key"])
