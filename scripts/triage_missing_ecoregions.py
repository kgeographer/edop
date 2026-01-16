#!/usr/bin/env python3
"""
Triage missing ecoregions to find potential Wikipedia matches.

Outputs a TSV with categories:
- strong_match: high-confidence title found (score >= 85)
- partial_match: possible match needs review (score 60-85)
- redirect: exact title redirects somewhere
- no_match: no good candidates found
"""
import argparse
import csv
import time
import sys
from typing import Dict, Any, List, Tuple, Optional
import requests
from rapidfuzz import fuzz

API = "https://en.wikipedia.org/w/api.php"


def mw_query(session: requests.Session, params: Dict[str, Any]) -> Dict[str, Any]:
    base = {"format": "json", "formatversion": 2}
    r = session.get(API, params={**base, **params}, timeout=30)
    r.raise_for_status()
    return r.json()


def check_redirect(session: requests.Session, title: str) -> Optional[Dict[str, Any]]:
    """Check if exact title exists or redirects. Returns page info or None."""
    j = mw_query(session, {
        "action": "query",
        "titles": title,
        "redirects": 1,
        "prop": "info",
        "inprop": "url",
    })
    q = j.get("query", {})
    pages = q.get("pages", [])
    redirects = q.get("redirects", [])

    if not pages:
        return None

    p = pages[0]
    if p.get("missing"):
        return None

    return {
        "pageid": p.get("pageid"),
        "title": p.get("title"),
        "fullurl": p.get("fullurl"),
        "redirected_from": redirects[0]["from"] if redirects else None,
    }


def search_candidates(session: requests.Session, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for candidate articles."""
    j = mw_query(session, {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "srprop": "snippet|titlesnippet",
    })
    hits = (j.get("query", {}).get("search")) or []
    return [{"title": h["title"], "snippet": h.get("snippet", "")} for h in hits]


def score_match(eco_name: str, candidate: str) -> float:
    """Score how well a candidate matches the eco_name."""
    # Use token_set_ratio which handles word order and partial matches well
    return fuzz.token_set_ratio(eco_name.lower(), candidate.lower())


def triage_ecoregion(session: requests.Session, eco_id: int, eco_name: str) -> Dict[str, Any]:
    """Triage a single ecoregion. Returns classification result."""
    result = {
        "eco_id": eco_id,
        "eco_name": eco_name,
        "status": "no_match",
        "best_title": "",
        "best_url": "",
        "score": 0,
        "redirected_from": "",
        "candidates": "",
        "notes": "",
    }

    # First, check if exact title exists or redirects
    exact = check_redirect(session, eco_name)
    if exact:
        score = score_match(eco_name, exact["title"])
        result["best_title"] = exact["title"]
        result["best_url"] = exact["fullurl"]
        result["score"] = score

        if exact.get("redirected_from"):
            result["status"] = "redirect"
            result["redirected_from"] = exact["redirected_from"]
            result["notes"] = f"Redirects to: {exact['title']}"
        elif score >= 85:
            result["status"] = "strong_match"
        else:
            result["status"] = "partial_match"
        return result

    # Search for candidates
    candidates = search_candidates(session, eco_name, limit=5)
    if not candidates:
        result["notes"] = "No search results"
        return result

    result["candidates"] = " | ".join(c["title"] for c in candidates[:3])

    # Score each candidate
    scored = [(c, score_match(eco_name, c["title"])) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_candidate, best_score = scored[0]
    result["best_title"] = best_candidate["title"]
    result["score"] = best_score

    # Get URL for best candidate
    info = check_redirect(session, best_candidate["title"])
    if info:
        result["best_url"] = info["fullurl"]

    # Classify
    if best_score >= 85:
        result["status"] = "strong_match"
    elif best_score >= 60:
        result["status"] = "partial_match"
        result["notes"] = f"Score {best_score:.0f}, review needed"
    else:
        result["status"] = "no_match"
        result["notes"] = f"Best score only {best_score:.0f}"

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="TSV with eco_id, eco_name columns")
    ap.add_argument("--output", required=True, help="Output TSV with triage results")
    ap.add_argument("--sleep", type=float, default=0.3, help="Delay between API calls")
    args = ap.parse_args()

    # Load missing ecoregions
    missing = []
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                missing.append((int(parts[0]), parts[1]))

    print(f"Loaded {len(missing)} missing ecoregions", file=sys.stderr)

    session = requests.Session()
    session.headers["User-Agent"] = "EDOP/0.1 (ecoregion triage; https://github.com/WorldHistoricalGazetteer/edop)"

    results = []
    counts = {"strong_match": 0, "partial_match": 0, "redirect": 0, "no_match": 0}

    for i, (eco_id, eco_name) in enumerate(missing, start=1):
        result = triage_ecoregion(session, eco_id, eco_name)
        results.append(result)
        counts[result["status"]] += 1

        if i % 10 == 0 or i == len(missing):
            print(f"[{i}/{len(missing)}] strong={counts['strong_match']} partial={counts['partial_match']} "
                  f"redirect={counts['redirect']} no_match={counts['no_match']}", file=sys.stderr)

        time.sleep(args.sleep)

    # Write output
    fieldnames = ["eco_id", "eco_name", "status", "best_title", "best_url", "score",
                  "redirected_from", "candidates", "notes"]
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Strong matches:  {counts['strong_match']}", file=sys.stderr)
    print(f"  Partial matches: {counts['partial_match']}", file=sys.stderr)
    print(f"  Redirects:       {counts['redirect']}", file=sys.stderr)
    print(f"  No match:        {counts['no_match']}", file=sys.stderr)
    print(f"\nWrote: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
