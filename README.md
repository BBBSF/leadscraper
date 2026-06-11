# BBB Bay Area Lead Scraper

A practical Python starter repo for collecting recurring public lead signals for Better Business Bureau sales prospecting in the SF Bay Area.

This is designed for **Codex to improve and maintain**, with the option to run on GitHub Actions, Apify, or a small server.

## What it pulls

Configured sources in `config/sources.yaml`:

1. **SF registered business locations** — DataSF Socrata API, dataset `g8m3-pdis`.
2. **SF building permits** — DataSF Socrata API, dataset `i98e-djp9`.
3. **SF building permit contacts** — DataSF Socrata API, dataset `3pee-9qhc`.
4. **Berkeley business licenses** — Berkeley Socrata API, dataset `rwnf-bu3w`.
5. **SF Chamber directory** — public GrowthZone-style alpha listing pages.
6. **Oakland Chamber directory** — public GrowthZone-style alpha listing pages.
7. **Marin Builders Association directory** — public GrowthZone-style alpha listing pages.
8. **CSLB manual ingest** — reads CSV/XLS files downloaded from the official CSLB Public Data Portal.

## What it outputs

The command creates:

- `data/output/bbb_leads_all.csv`
- `data/output/bbb_leads_deduped_scored.csv`
- `data/output/bbb_leads_high_priority.csv`
- `data/output/bbb_leads_export.xlsx`
- one `raw_SOURCE.csv` file per source for troubleshooting

Standard fields include:

```text
business_name, legal_name, category, source, source_url, record_url,
address, city, state, zip, phone, website, email,
license_number, license_status, permit_number, permit_date, permit_value,
business_start_date, date_scraped, lead_score, reason_to_call, raw_category
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m bbb_lead_scraper.cli list-sources
python -m bbb_lead_scraper.cli run --sources all --days-back 90
```

For a smaller first run:

```bash
python -m bbb_lead_scraper.cli run \
  --sources datasf_registered_business_locations,sf_building_permits,berkeley_business_licenses \
  --days-back 90
```

## CSLB workflow

CSLB provides official public downloads, including contractor lists by classification/county and statewide license master files. Download the file from CSLB, save it as something like:

```text
data/manual_inputs/cslb_2026_06_10.csv
```

Then run:

```bash
python -m bbb_lead_scraper.cli run --sources cslb_manual_ingest
```

Why manual ingest instead of a brittle form-bot? CSLB already offers CSV/XLS downloads. Treat that as a sanctioned source and avoid a fragile browser automation script unless you truly need it.

## Scheduling

### GitHub Actions

The included workflow `.github/workflows/weekly-leads.yml` runs weekly and uploads the CSV/XLSX exports as artifacts.

### Apify

Use the included `Dockerfile`, connect the repo to an Apify Python Actor, and run:

```bash
python -m bbb_lead_scraper.cli run --sources all --days-back 90 --out-dir /storage/key_value_stores/default
```

For chamber pages and JavaScript/form-heavy targets, Apify + Playwright is often the best production setup. Codex should still be used to modify the scraper code.

## Compliance guardrails

- Prefer official APIs and downloadable open-data files.
- Do not scrape Google Maps or LinkedIn.
- Use Google Places, Yelp, or other official APIs for enrichment.
- Respect robots.txt, site terms, rate limits, and opt-out requirements.
- Treat this as sales prospecting data, not a consumer data warehouse.

## Give this to Codex

Open `PROMPT_FOR_CODEX.md` and paste it into Codex with this repo attached.

## Tests

```bash
pytest
```
