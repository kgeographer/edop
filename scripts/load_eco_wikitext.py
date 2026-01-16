#!/usr/bin/env python3
"""
Load Wikipedia extracts from JSONL into public.eco_wikitext table.

Usage:
    python scripts/load_eco_wikitext.py --input output/wiki_extracts_refilled.jsonl
"""
import argparse
import json
import os
from datetime import datetime

import psycopg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to wiki_extracts JSONL file")
    ap.add_argument("--dry-run", action="store_true", help="Parse and validate without inserting")
    args = ap.parse_args()

    # Database connection from environment
    conn_params = {
        "host": os.getenv("PGHOST", "localhost"),
        "port": os.getenv("PGPORT", "5432"),
        "dbname": os.getenv("PGDATABASE", "edop"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", ""),
    }

    # Load records from JSONL
    records = []
    skipped = 0
    for line in open(args.input, "r", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)

        # Skip records without text
        if not (rec.get("extract_text") or "").strip():
            skipped += 1
            continue

        # Parse rev_timestamp if present (ISO format from Wikipedia)
        rev_ts = None
        if rec.get("rev_timestamp"):
            try:
                rev_ts = datetime.fromisoformat(rec["rev_timestamp"].replace("Z", "+00:00"))
            except ValueError:
                pass

        records.append({
            "eco_id": rec["eco_id"],
            "wiki_title": rec.get("wiki_title") or rec.get("eco_name"),
            "wiki_url": rec.get("fullurl"),
            "extract_text": rec["extract_text"],
            "rev_timestamp": rev_ts,
            "revid": rec.get("revid"),
            "source": rec.get("source", "enwiki"),
        })

    print(f"Loaded {len(records)} records with text, skipped {skipped} empty")

    if args.dry_run:
        print("Dry run - not inserting")
        return

    # Insert into database
    with psycopg.connect(**conn_params) as conn:
        with conn.cursor() as cur:
            # Truncate existing data
            cur.execute("TRUNCATE public.eco_wikitext")

            # Insert records
            inserted = 0
            for rec in records:
                try:
                    cur.execute("""
                        INSERT INTO public.eco_wikitext
                            (eco_id, wiki_title, wiki_url, extract_text, rev_timestamp, revid, source)
                        VALUES
                            (%(eco_id)s, %(wiki_title)s, %(wiki_url)s, %(extract_text)s,
                             %(rev_timestamp)s, %(revid)s, %(source)s)
                        ON CONFLICT (eco_id) DO UPDATE SET
                            wiki_title = EXCLUDED.wiki_title,
                            wiki_url = EXCLUDED.wiki_url,
                            extract_text = EXCLUDED.extract_text,
                            rev_timestamp = EXCLUDED.rev_timestamp,
                            revid = EXCLUDED.revid,
                            harvested_at = now(),
                            source = EXCLUDED.source
                    """, rec)
                    inserted += 1
                except Exception as e:
                    print(f"Error inserting eco_id={rec['eco_id']}: {e}")

            conn.commit()

    print(f"Inserted {inserted} records into public.eco_wikitext")


if __name__ == "__main__":
    main()
