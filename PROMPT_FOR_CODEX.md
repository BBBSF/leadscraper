# Prompt to give Codex

You are working in this repo. Your task is to run, test, and harden a recurring BBB Bay Area sales lead scraper.

Goals:
1. Run `python -m bbb_lead_scraper.cli list-sources` and inspect the configured sources.
2. Run `python -m bbb_lead_scraper.cli run --sources datasf_registered_business_locations,sf_building_permits,berkeley_business_licenses --days-back 90`.
3. Fix any source-specific column mapping issues by updating `bbb_lead_scraper/normalize.py` and/or `config/sources.yaml`.
4. Add source-specific parsers only where generic normalization is weak.
5. Keep the standardized output columns stable for CRM import.
6. Do not scrape Google Maps or LinkedIn. Use official APIs for enrichment.
7. Add tests for any parser you change.

Success criteria:
- `pytest` passes.
- `data/output/bbb_leads_deduped_scored.csv` exists.
- `data/output/bbb_leads_high_priority.csv` exists.
- High-priority rows have a useful `reason_to_call`.
