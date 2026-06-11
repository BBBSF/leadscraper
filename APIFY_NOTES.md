# Apify production notes

This repo is intentionally plain Python so Codex can read and modify it easily.

For Apify:
1. Create a new Python Actor.
2. Upload this repo or connect GitHub.
3. Set the Actor command to:
   python -m bbb_lead_scraper.cli run --sources all --days-back 90 --out-dir /storage/key_value_stores/default
4. Store `SOCRATA_APP_TOKEN` as an environment variable if you have one.
5. Schedule weekly or daily runs.
6. Export `bbb_leads_high_priority.csv` to Google Sheets, Make, Zapier, or CRM import.

Practical recommendation:
- API/open-data pulls can run in GitHub Actions or Apify.
- Browser/form-heavy sources should eventually become dedicated Apify Actors with Playwright.
- Keep Codex as the maintenance mechanic and Apify as the scheduler/operator.
