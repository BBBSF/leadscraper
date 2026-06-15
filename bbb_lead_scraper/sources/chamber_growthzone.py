from __future__ import annotations

import logging
import re
import string
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from bbb_lead_scraper.http import HttpClient
from bbb_lead_scraper.normalize import clean_text, extract_phone, extract_zip

log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


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
        self.profile_enrich_limit = int(cfg.get("profile_enrich_limit", 100))
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
        if self.cfg.get("enrich_profiles", True):
            records = self._enrich_records(records)
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
                    "website": "",
                    "email": "",
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
                        "website": "",
                        "email": "",
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

    def _enrich_records(self, records: list[dict[str, str]]) -> list[dict[str, str]]:
        enriched: list[dict[str, str]] = []
        cache: dict[str, dict[str, str]] = {}
        enriched_count = 0
        for rec in records:
            url = rec.get("record_url", "")
            if enriched_count >= self.profile_enrich_limit or not self._should_enrich_url(url):
                enriched.append(rec)
                continue
            if url not in cache:
                try:
                    cache[url] = self._parse_profile(self.client.get(url).text, url)
                except Exception as exc:  # noqa: BLE001 - profile enrichment should not kill source fetch
                    log.debug("Could not enrich %s: %s", url, exc)
                    cache[url] = {}
                enriched_count += 1
            rec = dict(rec)
            for key, value in cache[url].items():
                if value and not rec.get(key):
                    rec[key] = value
            enriched.append(rec)
        return enriched

    def _should_enrich_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        base_host = urlparse(self.base_url or "").netloc.lower()
        return bool(parsed.netloc and parsed.netloc.lower() == base_host and "/member/" in parsed.path)

    def _parse_profile(self, html: str, profile_url: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        text = clean_text(soup.get_text(" ", strip=True))
        email = self._extract_profile_email(soup, text)
        phone = extract_phone(text)
        website = self._extract_profile_website(soup, profile_url)
        return {"email": email, "phone": phone, "website": website}

    def _extract_profile_email(self, soup: BeautifulSoup, text: str) -> str:
        for link in soup.select("a[href^=mailto]"):
            href = link.get("href", "")
            candidate = href.split(":", 1)[-1].split("?", 1)[0]
            if self._usable_email(candidate):
                return candidate
        for candidate in EMAIL_RE.findall(text):
            if self._usable_email(candidate):
                return candidate
        return ""

    def _extract_profile_website(self, soup: BeautifulSoup, profile_url: str) -> str:
        links = soup.select("a[href]")
        preferred = [
            link for link in links
            if "website" in clean_text(link.get_text(" ", strip=True)).lower()
        ]
        for link in preferred:
            href = urljoin(profile_url, link.get("href", ""))
            if self._usable_website(href):
                return href
        return ""

    def _usable_email(self, email: str) -> bool:
        email = clean_text(email).lower()
        if not email or "@" not in email:
            return False
        host = email.split("@", 1)[-1]
        base_host = urlparse(self.base_url or "").netloc.lower()
        return not (
            host in base_host
            or "chamber" in host
            or "marinbuilders" in host
            or "growthzone" in host
            or "chambermaster" in host
        )

    def _usable_website(self, href: str) -> bool:
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        host = parsed.netloc.lower()
        base_host = urlparse(self.base_url or "").netloc.lower()
        blocked = (
            base_host,
            "sfchamber.com",
            "oaklandchamber.com",
            "marinbuilders.com",
            "chambermaster.com",
            "growthzone.com",
            "facebook.com",
            "instagram.com",
            "linkedin.com",
            "twitter.com",
            "x.com",
            "pinterest.com",
        )
        return not any(block and block in host for block in blocked)

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
