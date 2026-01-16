#!/usr/bin/env python3
"""
Fetch Wikipedia extracts for review candidates.
Adds extract_text and extract_preview columns to the review TSV.
"""
import argparse
import csv
import time
import sys
from typing import Dict, Any, Optional
import requests


API = "https://en.wikipedia.org/w/api.php"


def mw_query(session: requests.Session, params: Dict[str, Any]) -> Dict[str, Any]:
    base = {"format": "json", "formatversion": 2}
    r = session.get(API, params={**base, **params}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_extract(session: requests.Session, title: str) -> Optional[Dict[str, Any]]:
    """Fetch extract for a single title."""
    j = mw_query(session, {
        "action": "query",
        "titles": title,
        "redirects": 1,
        "prop": "extracts|info|revisions",
        "explaintext": 1,
        "exsectionformat": "plain",
        "rvprop": "ids|timestamp",
        "inprop": "url",
    })
    pages = j.get("query", {}).get("pages", [])
    if not pages:
        return None

    p = pages[0]
    if p.get("missing"):
        return None

    rev = (p.get("revisions") or [{}])[0] if p.get("revisions") else {}
    return {
        "wiki_title": p.get("title"),
        "fullurl": p.get("fullurl"),
        "extract_text": p.get("extract") or "",
        "revid": rev.get("revid"),
        "rev_timestamp": rev.get("timestamp"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Review TSV from triage")
    ap.add_argument("--output", required=True, help="Output TSV with extracts")
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    # Load review candidates
    with open(args.input, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Loaded {len(rows)} candidates", file=sys.stderr)

    session = requests.Session()
    session.headers["User-Agent"] = "EDOP/0.1 (ecoregion review; https://github.com/WorldHistoricalGazetteer/edop)"

    # Add new columns
    new_fieldnames = list(fieldnames) + ["extract_len", "extract_preview"]

    fetched = 0
    empty = 0

    for i, row in enumerate(rows, start=1):
        title = row.get("best_title", "").strip()
        if not title:
            row["extract_len"] = "0"
            row["extract_preview"] = ""
            empty += 1
            continue

        result = fetch_extract(session, title)
        if result and result.get("extract_text"):
            text = result["extract_text"]
            row["extract_len"] = str(len(text))
            # First 150 chars, clean up newlines
            preview = text[:150].replace("\n", " ").replace("\t", " ")
            if len(text) > 150:
                preview += "..."
            row["extract_preview"] = preview
            fetched += 1
        else:
            row["extract_len"] = "0"
            row["extract_preview"] = "[NO EXTRACT]"
            empty += 1

        if i % 20 == 0 or i == len(rows):
            print(f"[{i}/{len(rows)}] fetched={fetched} empty={empty}", file=sys.stderr)

        time.sleep(args.sleep)

    # Write output
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. fetched={fetched} empty={empty}", file=sys.stderr)
    print(f"Wrote: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
