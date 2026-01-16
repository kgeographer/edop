#!/usr/bin/env python3
"""
Fetch Wikipedia extracts for reviewed/accepted ecoregion candidates.

Handles two cases:
- accept=y: fetch full article extract
- section specified: fetch specific section(s) from article
"""
import argparse
import csv
import json
import re
import time
import sys
from typing import Dict, Any, Optional, List
import requests

API = "https://en.wikipedia.org/w/api.php"


def mw_query(session: requests.Session, params: Dict[str, Any]) -> Dict[str, Any]:
    base = {"format": "json", "formatversion": 2}
    r = session.get(API, params={**base, **params}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_full_extract(session: requests.Session, title: str) -> Optional[Dict[str, Any]]:
    """Fetch full article extract."""
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


def fetch_section_extract(session: requests.Session, title: str, section_names: List[str]) -> Optional[Dict[str, Any]]:
    """Fetch specific section(s) from an article."""
    # First get section list
    j = mw_query(session, {
        "action": "parse",
        "page": title,
        "prop": "sections",
    })

    if "error" in j:
        return None

    sections = j.get("parse", {}).get("sections", [])

    # Find matching section indices
    section_indices = []
    for sec in sections:
        sec_title = sec.get("line", "").strip()
        for name in section_names:
            if name.lower() in sec_title.lower() or sec_title.lower() in name.lower():
                section_indices.append(sec.get("index"))
                break

    if not section_indices:
        print(f"  Warning: no sections matched {section_names} in {title}", file=sys.stderr)
        return None

    # Fetch each section's content
    combined_text = []
    for idx in section_indices:
        j = mw_query(session, {
            "action": "parse",
            "page": title,
            "section": idx,
            "prop": "wikitext",
        })
        wikitext_data = j.get("parse", {}).get("wikitext", "")
        # Handle both string and dict formats
        if isinstance(wikitext_data, dict):
            wikitext = wikitext_data.get("*", "")
        else:
            wikitext = wikitext_data
        # Basic wikitext to plain text conversion
        plain = wikitext_to_plain(wikitext)
        if plain.strip():
            combined_text.append(plain.strip())

    if not combined_text:
        return None

    # Get page metadata
    j = mw_query(session, {
        "action": "query",
        "titles": title,
        "redirects": 1,
        "prop": "info|revisions",
        "rvprop": "ids|timestamp",
        "inprop": "url",
    })
    pages = j.get("query", {}).get("pages", [])
    p = pages[0] if pages else {}
    rev = (p.get("revisions") or [{}])[0] if p.get("revisions") else {}

    return {
        "wiki_title": p.get("title"),
        "fullurl": p.get("fullurl"),
        "extract_text": "\n\n".join(combined_text),
        "revid": rev.get("revid"),
        "rev_timestamp": rev.get("timestamp"),
    }


def wikitext_to_plain(wikitext: str) -> str:
    """Basic conversion of wikitext to plain text."""
    text = wikitext
    # Remove references
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'<ref[^/]*/>', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove templates (simplified - nested templates may not fully resolve)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    # Convert links [[link|text]] -> text, [[link]] -> link
    text = re.sub(r'\[\[[^|\]]+\|([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # Remove external links [url text] -> text
    text = re.sub(r'\[https?://[^\s\]]+ ([^\]]+)\]', r'\1', text)
    text = re.sub(r'\[https?://[^\]]+\]', '', text)
    # Remove bold/italic
    text = re.sub(r"'{2,}", '', text)
    # Remove section headers but keep text
    text = re.sub(r'^=+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*=+$', '', text, flags=re.MULTILINE)
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Reviewed TSV file")
    ap.add_argument("--output", required=True, help="Output JSONL file")
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    # Load reviewed candidates
    rows = []
    with open(args.input, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            accept = (row.get("accept") or "").strip().lower()
            section = (row.get("section") or "").strip()
            # Include if accept=y OR section is specified
            if accept == "y" or section:
                rows.append(row)

    print(f"Loaded {len(rows)} candidates to fetch", file=sys.stderr)

    session = requests.Session()
    session.headers["User-Agent"] = "EDOP/0.1 (ecoregion extracts; https://github.com/WorldHistoricalGazetteer/edop)"

    results = []
    success = 0
    failed = 0

    for i, row in enumerate(rows, start=1):
        eco_id = int(row["eco_id"])
        eco_name = row["eco_name"]
        title = row["best_title"]
        url = row["best_url"]
        section = (row.get("section") or "").strip()

        if section:
            # Fetch specific section(s)
            section_names = [s.strip() for s in section.split(";")]
            print(f"[{i}/{len(rows)}] {eco_name} -> sections {section_names}", file=sys.stderr)
            result = fetch_section_extract(session, title, section_names)
        else:
            # Fetch full article
            print(f"[{i}/{len(rows)}] {eco_name} -> {title}", file=sys.stderr)
            result = fetch_full_extract(session, title)

        if result and result.get("extract_text"):
            rec = {
                "eco_id": eco_id,
                "eco_name": eco_name,
                "wiki_title": result["wiki_title"],
                "fullurl": result["fullurl"] or url,
                "extract_text": result["extract_text"],
                "revid": result.get("revid"),
                "rev_timestamp": result.get("rev_timestamp"),
                "source": "enwiki",
            }
            results.append(rec)
            success += 1
        else:
            print(f"  FAILED: no extract for {eco_name}", file=sys.stderr)
            failed += 1

        time.sleep(args.sleep)

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nDone. success={success} failed={failed}", file=sys.stderr)
    print(f"Wrote: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
