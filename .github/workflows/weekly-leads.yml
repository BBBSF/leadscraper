name: Weekly BBB lead scrape

on:
  workflow_dispatch:
  schedule:
    # Mondays at 6:15am Pacific during PST/PDT-ish UTC compromise.
    - cron: "15 14 * * 1"

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run lead scraper
        env:
          SOCRATA_APP_TOKEN: ${{ secrets.SOCRATA_APP_TOKEN }}
        run: |
          python -m bbb_lead_scraper.cli run --sources all --days-back 90 --out-dir data/output
      - name: Upload exports
        uses: actions/upload-artifact@v4
        with:
          name: bbb-leads-export
          path: data/output/*
