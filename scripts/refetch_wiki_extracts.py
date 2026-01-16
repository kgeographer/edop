#!/usr/bin/env python3
"""
Refetch Wikipedia extracts for records with empty extract_text.

NOTE: Fetches one title at a time because MediaWiki's extracts API
only returns full article text for 1 page per request when using
explaintext=1 without exintro=1.
"""
import argparse, json, time, sys
from typing import Dict, Any, Optional
import requests


def mw_query(session: requests.Session, api: str, params: Dict[str, Any]) -> Dict[str, Any]:
    base = {"format": "json", "formatversion": 2}
    r = session.get(api, params={**base, **params}, timeout=60)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"MediaWiki error: {j['error']}")
    return j


def fetch_extract_for_title(session: requests.Session, api: str, title: str) -> Optional[Dict[str, Any]]:
    """Fetch full extract for a single title. Returns None if page missing."""
    j = mw_query(session, api, {
        "action": "query",
        "redirects": 1,
        "prop": "extracts|info|revisions",
        "explaintext": 1,
        "exsectionformat": "plain",
        "rvprop": "ids|timestamp",
        "rvslots": "main",
        "inprop": "url",
        "titles": title,
    })
    q = j.get("query", {}) or {}
    pages = q.get("pages") or []

    if not pages:
        return None

    p = pages[0]
    if p.get("missing"):
        return None

    rev = ((p.get("revisions") or [{}])[0]) if p.get("revisions") else {}
    return {
        "wiki_title": p.get("title"),
        "pageid": p.get("pageid"),
        "fullurl": p.get("fullurl"),
        "extract_text": p.get("extract") or "",
        "revid": rev.get("revid"),
        "rev_timestamp": rev.get("timestamp"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Existing wiki_extracts.jsonl")
    ap.add_argument("--out", dest="out_path", required=True, help="Output jsonl with refilled extracts")
    ap.add_argument("--sleep", type=float, default=0.2, help="Delay between requests (seconds)")
    ap.add_argument("--retries", type=int, default=3, help="Retry attempts per request")
    ap.add_argument("--progress-every", type=int, default=50, help="Print progress every N records")
    args = ap.parse_args()

    API = "https://en.wikipedia.org/w/api.php"

    # Load records
    records = []
    targets = []  # list of (index, title_for_refetch)
    for line in open(args.in_path, "r", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        records.append(rec)
        if not (rec.get("extract_text") or "").strip():
            # prefer wiki_title if present; else fallback to eco_name
            t = (rec.get("wiki_title") or rec.get("eco_name") or "").strip()
            if t:
                targets.append((len(records) - 1, t))

    print(f"Input records: {len(records)}")
    print(f"Empty extract_text records to refill: {len(targets)}")

    if not targets:
        print("Nothing to do.")
        with open(args.out_path, "w", encoding="utf-8") as out:
            for rec in records:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return

    session = requests.Session()
    session.headers["User-Agent"] = "EDOP/0.1 (ecoregion wiki extracts; https://github.com/WorldHistoricalGazetteer/edop)"

    filled = 0
    missing = 0
    errors = 0
    start = time.time()

    for i, (idx, title) in enumerate(targets, start=1):
        attempt = 0
        result = None

        while attempt < args.retries:
            attempt += 1
            try:
                result = fetch_extract_for_title(session, API, title)
                break
            except Exception as e:
                if attempt < args.retries:
                    print(f"[{i}] error attempt {attempt}/{args.retries} for '{title}': {e}", file=sys.stderr)
                    time.sleep(max(args.sleep, 1.0))
                else:
                    print(f"[{i}] FAILED after {args.retries} attempts: '{title}': {e}", file=sys.stderr)
                    errors += 1

        if result and result.get("extract_text"):
            r = records[idx]
            r["extract_text"] = result["extract_text"]
            r["wiki_title"] = result.get("wiki_title", r.get("wiki_title"))
            r["pageid"] = result.get("pageid", r.get("pageid"))
            r["fullurl"] = result.get("fullurl", r.get("fullurl"))
            r["revid"] = result.get("revid", r.get("revid"))
            r["rev_timestamp"] = result.get("rev_timestamp", r.get("rev_timestamp"))
            filled += 1
        elif result is None:
            missing += 1

        if i % args.progress_every == 0 or i == len(targets):
            dt = time.time() - start
            rate = i / dt if dt > 0 else 0
            eta = (len(targets) - i) / rate if rate > 0 else 0
            print(f"[{i}/{len(targets)}] filled={filled} missing={missing} errors={errors} "
                  f"time={dt:.1f}s eta={eta:.0f}s", flush=True)

        time.sleep(args.sleep)

    # Write output
    with open(args.out_path, "w", encoding="utf-8") as out:
        for rec in records:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    dt = time.time() - start
    print(f"\nDone in {dt:.1f}s. filled={filled} missing={missing} errors={errors}")
    print(f"Wrote: {args.out_path}")


if __name__ == "__main__":
    main()
