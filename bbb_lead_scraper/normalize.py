from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

STANDARD_COLUMNS = [
    "business_name",
    "legal_name",
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
        "business", "organization", "applicant", "contact_name", "contractor_name", "ownership_name",
    ],
    "legal_name": ["legal_name", "ownership_name", "owner_name", "licensee_name"],
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
    # Fuzzy-ish fallback: exact suffix/prefix contains, avoids heavy dependency.
    for c in candidates:
        wanted = c.lower()
        for actual_lower, actual in lower_to_actual.items():
            if wanted == actual_lower or wanted in actual_lower or actual_lower in wanted:
                return actual
    return None


def normalize_dataframe(df: pd.DataFrame, source_name: str, source_url: str, category: str = "") -> pd.DataFrame:
    """Normalize an arbitrary source dataframe into CRM-friendly lead columns."""
    out = pd.DataFrame(index=df.index)
    for col, candidates in CANDIDATES.items():
        picked = pick_column(df, candidates)
        out[col] = df[picked] if picked else ""

    out["business_name"] = out["business_name"].map(clean_text)
    out["legal_name"] = out["legal_name"].map(clean_text)
    out["raw_category"] = out["raw_category"].map(clean_text)
    out["category"] = category or out["raw_category"]
    out["source"] = source_name
    out["source_url"] = source_url
    out["date_scraped"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out["phone"] = out["phone"].map(normalize_phone)
    out["zip"] = out["zip"].map(clean_text).str.extract(r"(\d{5})", expand=False).fillna("")

    # Fill missing city/zip/phone from address or raw concatenated row text when possible.
    raw_text = df.astype(str).agg(" | ".join, axis=1)
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
