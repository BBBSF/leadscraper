from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from bbb_lead_scraper.config import load_config
from bbb_lead_scraper.google_places import enrich_dataframe
from bbb_lead_scraper.normalize import dedupe, normalize_dataframe
from bbb_lead_scraper.scoring import score_leads
from bbb_lead_scraper.sources import GrowthZoneDirectorySource, LocalFileSource, SocrataSource

log = logging.getLogger(__name__)


def build_source(name: str, cfg: dict[str, Any], project_root: Path):
    source_type = cfg.get("type")
    if source_type == "socrata":
        return SocrataSource(name, cfg)
    if source_type == "growthzone_directory":
        return GrowthZoneDirectorySource(name, cfg)
    if source_type == "local_file_ingest":
        return LocalFileSource(name, cfg, project_root=project_root)
    raise ValueError(f"Unknown source type for {name}: {source_type}")


def select_sources(all_sources: dict[str, dict[str, Any]], requested: str) -> dict[str, dict[str, Any]]:
    if requested == "all":
        return {name: cfg for name, cfg in all_sources.items() if cfg.get("enabled", True)}
    wanted = {s.strip() for s in requested.split(",") if s.strip()}
    missing = wanted - set(all_sources)
    if missing:
        raise ValueError(f"Unknown source(s): {', '.join(sorted(missing))}")
    return {name: all_sources[name] for name in wanted if all_sources[name].get("enabled", True)}


def run(args: argparse.Namespace) -> int:
    load_dotenv()
    project_root = Path(args.project_root).resolve()
    config = load_config(project_root / args.config)
    out_dir = project_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    source_cfgs = select_sources(config["sources"], args.sources)
    for name, cfg in source_cfgs.items():
        log.info("Fetching %s (%s)", name, cfg.get("description", cfg.get("type")))
        source = build_source(name, cfg, project_root=project_root)
        raw = source.fetch(days_back=args.days_back)
        raw_path = out_dir / f"raw_{name}.csv"
        raw.to_csv(raw_path, index=False)
        if raw.empty:
            log.warning("Skipping %s because it returned no rows", name)
            continue
        normalized = normalize_dataframe(
            raw,
            source_name=name,
            source_url=cfg.get("source_url", ""),
            category=cfg.get("category", ""),
        )
        frames.append(normalized)
        log.info("%s: %d rows", name, len(normalized))

    if not frames:
        log.error("No records returned from selected sources.")
        return 2

    combined = pd.concat(frames, ignore_index=True)
    scored = score_leads(combined, config.get("lead_scoring", {}))
    deduped = dedupe(scored)

    # Keep practical sales exports.
    all_path = out_dir / "bbb_leads_all.csv"
    deduped_path = out_dir / "bbb_leads_deduped_scored.csv"
    high_path = out_dir / "bbb_leads_high_priority.csv"
    xlsx_path = out_dir / "bbb_leads_export.xlsx"

    scored.to_csv(all_path, index=False)
    deduped.to_csv(deduped_path, index=False)
    deduped[deduped["lead_score"].fillna(0).astype(int) >= args.min_score].to_csv(high_path, index=False)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        deduped.to_excel(writer, sheet_name="Deduped scored leads", index=False)
        deduped[deduped["lead_score"].fillna(0).astype(int) >= args.min_score].to_excel(
            writer, sheet_name="High priority", index=False
        )
        scored.to_excel(writer, sheet_name="All raw-normalized", index=False)

    print(f"Wrote {len(scored):,} normalized records")
    print(f"Wrote {len(deduped):,} deduped leads")
    print(f"Exports:")
    print(f"  {deduped_path}")
    print(f"  {high_path}")
    print(f"  {xlsx_path}")
    return 0


def list_sources(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    config = load_config(project_root / args.config)
    for name, cfg in config["sources"].items():
        status = "enabled" if cfg.get("enabled", True) else "disabled"
        print(f"{name:36} {status:8} {cfg.get('type',''):22} {cfg.get('description','')}")
    return 0


def enrich_google_places(args: argparse.Namespace) -> int:
    load_dotenv()
    project_root = Path(args.project_root).resolve()
    input_path = project_root / args.input
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    enriched = enrich_dataframe(
        df,
        limit=args.limit,
        min_confidence=args.min_confidence,
        only_missing_phone=not args.include_existing_phone,
    )
    enriched.to_csv(output_path, index=False)

    attempted = enriched["google_enrichment_status"].fillna("").astype(str).str.strip().ne("")
    status_counts = enriched.loc[attempted, "google_enrichment_status"].value_counts().to_dict()
    phone_count = enriched.loc[attempted, "google_phone"].fillna("").astype(str).str.strip().ne("").sum()
    website_count = enriched.loc[attempted, "google_website"].fillna("").astype(str).str.strip().ne("").sum()
    print(f"Wrote enriched CSV: {output_path}")
    print(f"Google phone matches: {phone_count}")
    print(f"Google website matches: {website_count}")
    print(f"Statuses: {status_counts}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BBB Bay Area lead scraper")
    parser.add_argument("--project-root", default=".", help="Project root containing config/ and data/")
    parser.add_argument("--config", default="config/sources.yaml", help="Path to config file")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run one or more lead sources")
    run_p.add_argument("--sources", default="all", help="all or comma-separated source names")
    run_p.add_argument("--days-back", type=int, default=90, help="Recency window for API sources")
    run_p.add_argument("--out-dir", default="data/output", help="Output directory")
    run_p.add_argument("--min-score", type=int, default=45, help="High-priority export score threshold")
    run_p.set_defaults(func=run)

    list_p = sub.add_parser("list-sources", help="List configured sources")
    list_p.set_defaults(func=list_sources)

    enrich_p = sub.add_parser("enrich-google-places", help="Enrich an existing CSV with Google Places")
    enrich_p.add_argument("--input", required=True, help="Input CSV path relative to project root")
    enrich_p.add_argument("--output", required=True, help="Output CSV path relative to project root")
    enrich_p.add_argument("--limit", type=int, default=25, help="Maximum rows to enrich")
    enrich_p.add_argument("--min-confidence", type=int, default=70, help="Minimum match confidence to accept")
    enrich_p.add_argument(
        "--include-existing-phone",
        action="store_true",
        help="Also enrich rows that already have a phone number",
    )
    enrich_p.set_defaults(func=enrich_google_places)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
