import pandas as pd

from bbb_lead_scraper.normalize import dedupe, normalize_dataframe
from bbb_lead_scraper.scoring import score_leads


def test_normalize_basic_columns():
    raw = pd.DataFrame([
        {
            "dba_name": "Acme Roofing",
            "location_address": "123 Main St San Francisco CA 94103",
            "business_phone": "4155551212",
            "naics_code_description": "Roofing contractor",
        }
    ])
    out = normalize_dataframe(raw, "datasf", "https://example.com", "business_registry")
    assert out.loc[0, "business_name"] == "Acme Roofing"
    assert out.loc[0, "phone"] == "(415) 555-1212"
    assert out.loc[0, "zip"] == "94103"


def test_scoring_bbb_vertical():
    raw = pd.DataFrame([
        {
            "business_name": "Acme Roofing",
            "category": "licensed_contractor",
            "raw_category": "Roofing contractor",
            "source": "cslb_manual_ingest",
            "phone": "(415) 555-1212",
            "city": "San Francisco",
            "license_number": "123456",
        }
    ])
    out = score_leads(raw, {"high_value_keywords": ["roofing", "contractor"], "bay_area_cities": ["san francisco"]})
    assert int(out.loc[0, "lead_score"]) >= 60
    assert "reason_to_call" in out.columns


def test_dedupe_prefers_higher_score():
    raw = pd.DataFrame([
        {"business_name": "Acme Roofing", "phone": "(415) 555-1212", "zip": "94103", "address": "123 Main", "lead_score": 50},
        {"business_name": "Acme Roofing", "phone": "4155551212", "zip": "94103", "address": "123 Main", "lead_score": 80},
    ])
    out = dedupe(raw)
    assert len(out) == 1
    assert int(out.iloc[0]["lead_score"]) == 80
