from __future__ import annotations

import logging
import re
import string
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from bbb_lead_scraper.http import HttpClient
from bbb_lead_scraper.normalize import clean_text, extract_phone, extract_zip

log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")


class GrowthZoneDirectorySource:
    """Scrape public GrowthZone/ChamberMaster-style directory pages.

    This is intentionally conservative: it uses the public alpha listing pages and avoids
    login-only member-center content. If a site changes markup, the fallback text parser
    still recovers business name, address-ish lines, phone, and profile URL in many cases.
    """

    def __init__(self, name: str, cfg: dict[str, Any]):
        self.name = name
        self.cfg = cfg
        self.base_url = cfg.get("base_url") or cfg.get("source_url")
        self.alpha_url_template = cfg.get("alpha_url_template")
        self.max_pages_per_letter = int(cfg.get("max_pages_per_letter", 3))
        self.client = HttpClient()

    def _urls(self) -> list[str]:
        if not self.alpha_url_template:
            return [self.base_url]
        return [self.alpha_url_template.format(letter=letter) for letter in string.ascii_lowercase]

    def fetch(self, days_back: int | None = None) -> pd.DataFrame:  # noqa: ARG002 - not meaningful for chamber dirs
        records: list[dict[str, str]] = []
        for url in self._urls():
            try:
                html = self.client.get(url).text
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed fetching %s: %s", url, exc)
                continue
            records.extend(self._parse_page(html, url))
        return pd.DataFrame(records)

    def _parse_page(self, html: str, page_url: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        records: list[dict[str, str]] = []

        # Common GrowthZone/ChamberMaster containers; keep broad for resilience.
        containers = soup.select(
            ".mn-listing, .mn-company, .gz-card, .card, .member, .listing, li, .row"
        )
        seen_text: set[str] = set()
        for node in containers:
            text = clean_text(node.get_text(" ", strip=True))
            if len(text) < 8 or text in seen_text:
                continue
            seen_text.add(text)
            phone = extract_phone(text)
            zip_code = extract_zip(text)
            if not phone and not zip_code:
                continue

            name = self._extract_name(node, text)
            if not name or len(name) > 120 or self._bad_name(name):
                continue
            link = self._extract_link(node, page_url)
            address = self._extract_address(text, phone)
            records.append(
                {
                    "business_name": name,
                    "address": address,
                    "phone": phone,
                    "zip": zip_code,
                    "record_url": link,
                    "raw_category": "chamber directory",
                }
            )
        # Fallback: parse heading blocks only if broad container parsing found nothing.
        if not records:
            for heading in soup.find_all(["h3", "h4", "h5", "a"]):
                name = clean_text(heading.get_text(" ", strip=True))
                if not name or len(name) > 100:
                    continue
                parent = heading.find_parent() or heading
                text = clean_text(parent.get_text(" ", strip=True))
                phone = extract_phone(text)
                zip_code = extract_zip(text)
                if not phone and not zip_code:
                    continue
                records.append(
                    {
                        "business_name": name,
                        "address": self._extract_address(text, phone),
                        "phone": phone,
                        "zip": zip_code,
                        "record_url": self._extract_link(parent, page_url),
                        "raw_category": "chamber directory",
                    }
                )
        # De-duplicate nested containers that produced the same business.
        deduped: list[dict[str, str]] = []
        seen_keys: set[str] = set()
        for rec in records:
            key = (rec.get("business_name", "").lower(), rec.get("phone", ""), rec.get("zip", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(rec)
        return deduped

    @staticmethod
    def _bad_name(name: str) -> bool:
        low = name.strip().lower()
        if PHONE_RE.search(name):
            return True
        if re.match(r"^\d+\s", low):
            return True
        if re.search(r"\bca\s+9\d{4}\b", low):
            return True
        if low in {"contact us", "join us", "member login", "business directory"}:
            return True
        return False

    @staticmethod
    def _extract_name(node: Any, fallback_text: str) -> str:
        selectors = [".mn-title", ".mn-company-name", ".gz-card-title", "h1", "h2", "h3", "h4", "h5", "a"]
        for selector in selectors:
            found = node.select_one(selector) if hasattr(node, "select_one") else None
            if found:
                name = clean_text(found.get_text(" ", strip=True))
                if name and not PHONE_RE.search(name):
                    return name
        # Take text before a bullet/address/phone as last resort.
        text = re.split(r"\s{2,}|\s\*\s|\s\(\d{3}\)", fallback_text)[0]
        return clean_text(text[:120])

    @staticmethod
    def _extract_link(node: Any, page_url: str) -> str:
        link = node.find("a", href=True) if hasattr(node, "find") else None
        if link and link.get("href"):
            return urljoin(page_url, link["href"])
        return page_url

    @staticmethod
    def _extract_address(text: str, phone: str) -> str:
        t = text.replace(phone, "") if phone else text
        # Capture the likely street/city/zip chunk around a CA ZIP.
        zip_match = re.search(r"(.{0,120}\bCA\s+9\d{4}(?:-\d{4})?)", t, re.I)
        if zip_match:
            return clean_text(zip_match.group(1))
        return ""
