#!/usr/bin/env python3
"""
Sondr ICP Finder
Usage: python find_leads.py [--region "Boise, ID"] [--limit 30] [--config config.yaml]
"""

import argparse
import os
import sys
import yaml
from urllib.parse import urlparse

from dotenv import load_dotenv

from scraper.search import collect_urls
from scraper.fetch import fetch_site
from scraper.extract import extract_signals
from scraper.score import score_lead
from scraper.output import write_outputs

load_dotenv()


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def extract_company_name(url: str) -> str:
    """Best-effort company name from domain."""
    netloc = urlparse(url).netloc.lower().removeprefix("www.")
    name = netloc.split(".")[0]
    return name.replace("-", " ").replace("_", " ").title()


def run(config: dict, region_filter: str | None, limit: int) -> None:
    api_key = os.environ.get("SERPER_API_KEY") or config["search"].get("api_key", "")
    if not api_key:
        print("ERROR: SERPER_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    regions = config["regions"]
    if region_filter:
        regions = [r for r in regions if region_filter.lower() in r.lower()]
        if not regions:
            print(f"ERROR: No regions matched '{region_filter}'. Check config.yaml regions list.")
            sys.exit(1)

    category_terms = config["category_terms"]
    exclude_domains = config["exclude_domains"]
    national_keywords = config["national_brand_keywords"]
    weights = config["scoring"]
    fetch_cfg = config["fetch"]
    output_cfg = config["output"]

    leads_file = output_cfg["leads_file"]
    review_file = output_cfg["review_file"]
    max_leads = limit or output_cfg["max_leads"]

    print(f"\n=== Sondr ICP Finder ===")
    print(f"Regions : {regions}")
    print(f"Categories: {len(category_terms)}")
    print(f"Limit   : {max_leads} leads\n")

    # Step 1–3: Query generation, search, dedup/filter
    print("[ 1/4 ] Running search queries via Serper.dev...")
    candidates = collect_urls(
        regions=regions,
        category_terms=category_terms,
        api_key=api_key,
        exclude_domains=exclude_domains,
        results_per_query=config["search"]["results_per_query"],
        delay=fetch_cfg["request_delay_seconds"],
    )
    print(f"        {len(candidates)} unique domains after dedup/filter\n")

    # Steps 4–7: Fetch, extract, score
    leads = []
    for i, candidate in enumerate(candidates, 1):
        url = candidate["url"]
        company_name = extract_company_name(url)
        print(f"[ 2/4 ] ({i}/{len(candidates)}) Fetching {url}")

        fetch_result = fetch_site(
            url=url,
            timeout=fetch_cfg["timeout_seconds"],
            delay=fetch_cfg["request_delay_seconds"],
            max_pages=fetch_cfg["max_pages_per_site"],
        )

        signals = extract_signals(fetch_result)
        fit_score, score_flags = score_lead(
            signals=signals,
            weights=weights,
            national_keywords=national_keywords,
            company_name=company_name,
            url=url,
        )

        leads.append({
            "url": url,
            "root_domain": candidate["root_domain"],
            "region": candidate["region"],
            "category": candidate["category"],
            "company_name": company_name,
            "fit_score": fit_score,
            "score_flags": score_flags,
            "signals": signals,
        })

        status = f"score={fit_score}"
        if fit_score == 0:
            status += " (excluded)"
        print(f"           {status}")

    # Steps 8–9: Output
    print(f"\n[ 3/4 ] Writing output files...")
    n_leads, n_review = write_outputs(
        leads=leads,
        leads_path=leads_file,
        review_path=review_file,
        max_leads=max_leads,
    )

    print(f"\n=== Done ===")
    print(f"  Ranked leads  → {leads_file} ({n_leads} rows)")
    print(f"  Manual review → {review_file} ({n_review} rows)")


def main():
    parser = argparse.ArgumentParser(
        description="Find and score regional food distributor leads for Sondr outreach."
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help='Filter to a specific region, e.g. --region "Boise, ID"',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max leads to output (overrides config max_leads)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    run(config, region_filter=args.region, limit=args.limit)


if __name__ == "__main__":
    main()
