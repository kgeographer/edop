#!/usr/bin/env python3
"""
Harvest Wikipedia text for ecoregion names (batching to minimize requests).

Input:
  ecoregions_847.tsv  (expects at least: eco_id, eco_name)

Outputs:
  wiki_resolved.tsv
  wiki_missing.tsv
  wiki_extracts.jsonl

Install:
  pip install pandas requests rapidfuzz
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
from rapidfuzz import fuzz, process


API = "https://en.wikipedia.org/w/api.php"


def chunked(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def mw_query(session: requests.Session, params: Dict[str, Any]) -> Dict[str, Any]:
    base = {"format": "json", "formatversion": 2}
    r = session.get(API, params={**base, **params}, timeout=60)
    r.raise_for_status()
    return r.json()


def resolve_titles(
    session: requests.Session,
    titles: List[str],
    batch_size: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """
    Resolve titles -> page records (includes redirects), keyed by *original title* where possible.
    Returns dict: title_input -> {pageid, title, missing, ...}
    """
    out: Dict[str, Dict[str, Any]] = {}

    for batch in chunked(titles, batch_size):
        joined = "|".join(batch)
        j = mw_query(
            session,
            {
                "action": "query",
                "titles": joined,
                "redirects": 1,   # follow redirects
                "prop": "info",
                "inprop": "url",  # includes fullurl
            },
        )
        pages = (j.get("query") or {}).get("pages") or []
        # MediaWiki returns pages in an array under formatversion=2.
        # We can't always map back to each original input title cleanly without 'normalized'/'redirects' tables.
        # We'll key by returned page title first; then we'll also store missing by input.
        for p in pages:
            rec = {
                "pageid": p.get("pageid"),
                "wiki_title": p.get("title"),
                "fullurl": p.get("fullurl"),
                "missing": bool(p.get("missing")),
            }
            # We'll store by returned title; later we’ll join via exact match on input if possible.
            out[p.get("title", "")] = rec

        # Also mark obviously-missing inputs: if an input title doesn't appear in any returned titles,
        # we'll leave it for later logic. (Handled downstream.)

    return out


def search_candidates(
    session: requests.Session,
    query_str: str,
    limit: int = 5,
    sleep_s: float = 0.05,
) -> List[str]:
    j = mw_query(
        session,
        {
            "action": "query",
            "list": "search",
            "srsearch": query_str,
            "srlimit": limit,
        },
    )
    time.sleep(sleep_s)
    hits = ((j.get("query") or {}).get("search")) or []
    return [h["title"] for h in hits]


def pick_best_candidate(name: str, candidates: List[str]) -> Tuple[str, float]:
    if not candidates:
        return "", 0.0
    best, score, _ = process.extractOne(name, candidates, scorer=fuzz.token_set_ratio)
    return best, float(score)


def fetch_extracts_by_pageid(
    session: requests.Session,
    pageids: List[int],
    batch_size: int = 50,
) -> Dict[int, Dict[str, Any]]:
    """
    Fetch plain-text extracts + revision ids/timestamps in batches.
    """
    out: Dict[int, Dict[str, Any]] = {}
    for batch in chunked([str(pid) for pid in pageids], batch_size):
        joined = "|".join(batch)
        j = mw_query(
            session,
            {
                "action": "query",
                "pageids": joined,
                "prop": "extracts|revisions|info",
                "explaintext": 1,
                "exsectionformat": "plain",
                "rvprop": "ids|timestamp",
                "rvslots": "main",
                "inprop": "url",
            },
        )
        pages = (j.get("query") or {}).get("pages") or []
        for p in pages:
            pid = p.get("pageid")
            if not pid:
                continue
            rev = ((p.get("revisions") or [{}])[0]) if p.get("revisions") else {}
            out[int(pid)] = {
                "pageid": int(pid),
                "wiki_title": p.get("title"),
                "fullurl": p.get("fullurl"),
                "extract_text": p.get("extract", "") or "",
                "revid": rev.get("revid"),
                "rev_timestamp": rev.get("timestamp"),
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to ecoregions_847.tsv")
    ap.add_argument("--outdir", default="output/", help="Output directory")
    ap.add_argument("--lang", default="en", help="Wikipedia language code (default: en)")
    ap.add_argument("--batch", type=int, default=50, help="Titles/pageids per request (default 50)")
    ap.add_argument("--search_limit", type=int, default=5, help="Search candidates per miss")
    ap.add_argument("--min_score", type=float, default=80.0, help="Min fuzzy score to accept search match")
    args = ap.parse_args()

    api = f"https://{args.lang}.wikipedia.org/w/api.php"

    df = pd.read_csv(args.input, sep="\t")
    if "eco_id" not in df.columns or "eco_name" not in df.columns:
        raise SystemExit("Input TSV must contain columns: eco_id, eco_name")

    # Build session
    session = requests.Session()
    session.headers["User-Agent"] = "EDOP/0.1 (ecoregion text harvest; contact: you@yourdomain.example) requests"
    global API
    API = api

    eco_names = df["eco_name"].astype(str).tolist()

    # 1) First pass: attempt exact title resolve in batches.
    # We'll do a more direct approach: query per batch and map results back by looking for exact match
    resolved_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []

    # For exact resolving, we’ll query in batches but then attempt to match returned titles to inputs by:
    # - exact title equality (case-sensitive as MediaWiki normalizes)
    # - if not found, treat as missing for search fallback.
    for batch_idx, batch in enumerate(chunked(eco_names, args.batch), start=1):
        j = mw_query(
            session,
            {
                "action": "query",
                "titles": "|".join(batch),
                "redirects": 1,
                "prop": "info",
                "inprop": "url",
            },
        )
        pages = (j.get("query") or {}).get("pages") or []
        # Build a map of returned titles -> page record
        returned_by_title = {p.get("title", ""): p for p in pages if p.get("title")}

        # For each input title, see if it exists as returned title; otherwise mark missing.
        for name in batch:
            p = returned_by_title.get(name)
            if p and not p.get("missing"):
                resolved_rows.append(
                    {
                        "eco_name": name,
                        "wiki_title": p.get("title"),
                        "pageid": p.get("pageid"),
                        "fullurl": p.get("fullurl"),
                        "resolved_via": "exact_or_redirect_batch",
                        "match_score": 100.0,
                    }
                )
            else:
                missing_rows.append(
                    {
                        "eco_name": name,
                        "why": "not_found_in_exact_batch",
                    }
                )

        # Tiny pause just to be polite; you’ll only do ~17 passes
        time.sleep(0.05)

    # Merge back eco_id
    resolved_df = pd.DataFrame(resolved_rows).merge(df[["eco_id", "eco_name"]], on="eco_name", how="left")
    missing_df = pd.DataFrame(missing_rows).merge(df[["eco_id", "eco_name"]], on="eco_name", how="left")

    # 2) Search fallback for missing
    fallback_records: List[Dict[str, Any]] = []
    still_missing: List[Dict[str, Any]] = []

    for r in missing_df.itertuples(index=False):
        candidates = search_candidates(session, r.eco_name, limit=args.search_limit)
        best, score = pick_best_candidate(r.eco_name, candidates)
        if best and score >= args.min_score:
            # resolve best candidate to get pageid/fullurl
            j = mw_query(
                session,
                {
                    "action": "query",
                    "titles": best,
                    "redirects": 1,
                    "prop": "info",
                    "inprop": "url",
                },
            )
            pages = (j.get("query") or {}).get("pages") or []
            p = pages[0] if pages else {}
            if p and not p.get("missing") and p.get("pageid"):
                fallback_records.append(
                    {
                        "eco_id": r.eco_id,
                        "eco_name": r.eco_name,
                        "wiki_title": p.get("title"),
                        "pageid": p.get("pageid"),
                        "fullurl": p.get("fullurl"),
                        "resolved_via": "search_fallback",
                        "match_score": score,
                        "search_candidates": "|".join(candidates),
                    }
                )
            else:
                still_missing.append(
                    {
                        "eco_id": r.eco_id,
                        "eco_name": r.eco_name,
                        "best_candidate": best,
                        "best_score": score,
                        "search_candidates": "|".join(candidates),
                        "why": "candidate_resolve_failed",
                    }
                )
        else:
            still_missing.append(
                {
                    "eco_id": r.eco_id,
                    "eco_name": r.eco_name,
                    "best_candidate": best,
                    "best_score": score,
                    "search_candidates": "|".join(candidates),
                    "why": "no_good_search_match",
                }
            )

    fallback_df = pd.DataFrame(fallback_records)
    still_missing_df = pd.DataFrame(still_missing)

    # Combine resolved
    all_resolved = pd.concat(
        [
            resolved_df[["eco_id", "eco_name", "wiki_title", "pageid", "fullurl", "resolved_via", "match_score"]],
            fallback_df[["eco_id", "eco_name", "wiki_title", "pageid", "fullurl", "resolved_via", "match_score"]],
        ],
        ignore_index=True,
    ).drop_duplicates(subset=["eco_id", "pageid"], keep="first")

    # 3) Fetch extracts for resolved pageids (batched)
    pageids = [int(pid) for pid in all_resolved["pageid"].dropna().astype(int).unique().tolist()]
    extracts_by_pid = fetch_extracts_by_pageid(session, pageids, batch_size=args.batch)

    # Write JSONL for easy DB loading
    jsonl_path = f"{args.outdir.rstrip('/')}/wiki_extracts.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in all_resolved.itertuples(index=False):
            pid = int(r.pageid)
            ex = extracts_by_pid.get(pid, {})
            rec = {
                "eco_id": int(r.eco_id),
                "eco_name": r.eco_name,
                "wiki_title": r.wiki_title,
                "pageid": pid,
                "fullurl": r.fullurl,
                "resolved_via": r.resolved_via,
                "match_score": float(r.match_score),
                "revid": ex.get("revid"),
                "rev_timestamp": ex.get("rev_timestamp"),
                "extract_text": ex.get("extract_text", ""),
                "source": f"{args.lang}wiki",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Write TSV reports
    resolved_path = f"{args.outdir.rstrip('/')}/wiki_resolved.tsv"
    missing_path = f"{args.outdir.rstrip('/')}/wiki_missing.tsv"
    all_resolved.to_csv(resolved_path, sep="\t", index=False)
    still_missing_df.to_csv(missing_path, sep="\t", index=False)

    print(f"Resolved: {len(all_resolved)}")
    print(f"Missing : {len(still_missing_df)}")
    print(f"Wrote   : {resolved_path}")
    print(f"Wrote   : {missing_path}")
    print(f"Wrote   : {jsonl_path}")


if __name__ == "__main__":
    main()

