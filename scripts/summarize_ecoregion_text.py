#!/usr/bin/env python3
"""
Summarize ecoregion Wikipedia text using Claude Sonnet.

Reads from public.eco_wikitext, generates ~150-200 word summaries focused on
geography, climate, and ecology, then updates the summary column.

Usage:
    python scripts/summarize_ecoregion_text.py [--dry-run] [--limit N]

Requires:
    ANTHROPIC_API_KEY in environment or .env file
    pip install anthropic psycopg[binary] python-dotenv
"""

import argparse
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Check for API key before importing anthropic
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not found in environment or .env")
    print("Add to .env: ANTHROPIC_API_KEY=sk-ant-...")
    exit(1)

import anthropic
import psycopg

# Database connection
DB_PARAMS = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5435"),
    "dbname": os.getenv("PGDATABASE", "edop"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
}

# Claude client
client = anthropic.Anthropic(api_key=api_key)

SYSTEM_PROMPT = """You are a biogeographer writing concise, factual summaries of ecoregions for a geographic reference system.
Use only the information provided in the source text. Do not add external knowledge.
Write in clear, neutral encyclopedic prose. Use present tense for enduring features.
Focus on what makes this ecoregion distinctive and where it is located."""

USER_PROMPT = """Summarize this ecoregion in 150-200 words, focusing on:
- Geographic location and extent
- Terrain and landscape characteristics
- Climate (temperature, precipitation)
- Distinctive flora and fauna

Do not include the WWF ID or area statistics. End with a complete sentence.

--- SOURCE TEXT ---

{text}"""


def get_pending_records(conn, limit=None):
    """Fetch eco_wikitext records without summaries."""
    query = """
        SELECT w.eco_id, e.eco_name, w.wiki_title, w.extract_text, w.wiki_url
        FROM public.eco_wikitext w
        JOIN gaz."Ecoregions2017" e ON e.eco_id = w.eco_id
        WHERE w.summary IS NULL
          AND w.extract_text IS NOT NULL
          AND LENGTH(w.extract_text) > 100
        ORDER BY w.eco_id
    """
    if limit:
        query += f" LIMIT {limit}"

    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def summarize_text(eco_name: str, text: str) -> dict:
    """Call Claude Sonnet to summarize ecoregion text."""
    # Truncate if very long (shouldn't happen, but safety)
    max_chars = 20000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Text truncated...]"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT.format(text=text)
                }
            ]
        )

        summary = response.content[0].text.strip()

        return {
            "status": "ok",
            "summary": summary,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "summary": None
        }


def update_summary(conn, eco_id: int, summary: str):
    """Update the summary column for an ecoregion."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.eco_wikitext SET summary = %s WHERE eco_id = %s",
            (summary, eco_id)
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Summarize ecoregion Wikipedia text")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database")
    parser.add_argument("--limit", type=int, help="Limit number of records to process")
    args = parser.parse_args()

    print("Connecting to database...")
    conn = psycopg.connect(**DB_PARAMS)

    # Ensure summary column exists
    with conn.cursor() as cur:
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'eco_wikitext'
                      AND column_name = 'summary'
                ) THEN
                    ALTER TABLE public.eco_wikitext ADD COLUMN summary TEXT;
                END IF;
            END $$;
        """)
    conn.commit()

    print("Fetching records without summaries...")
    records = get_pending_records(conn, args.limit)
    print(f"Found {len(records)} records to process\n")

    if not records:
        print("Nothing to do!")
        return

    total_tokens = {"input": 0, "output": 0}
    success_count = 0
    error_count = 0

    for i, (eco_id, eco_name, wiki_title, text, wiki_url) in enumerate(records, 1):
        print(f"[{i:3d}/{len(records)}] {eco_name[:50]}...")

        result = summarize_text(eco_name, text)

        if result["status"] == "ok":
            summary = result["summary"]
            tokens_in = result["input_tokens"]
            tokens_out = result["output_tokens"]
            total_tokens["input"] += tokens_in
            total_tokens["output"] += tokens_out

            word_count = len(summary.split())
            print(f"         -> {word_count} words ({tokens_in}+{tokens_out} tokens)")

            if not args.dry_run:
                update_summary(conn, eco_id, summary)

            success_count += 1
        else:
            print(f"         -> ERROR: {result.get('error', 'unknown')}")
            error_count += 1

        # Rate limiting - be gentle
        time.sleep(0.3)

    conn.close()

    print(f"\n{'='*50}")
    print(f"Processed: {success_count} success, {error_count} errors")
    print(f"Tokens: {total_tokens['input']:,} input + {total_tokens['output']:,} output")

    # Cost estimate (Sonnet pricing: $3/M input, $15/M output)
    cost_input = (total_tokens["input"] / 1_000_000) * 3
    cost_output = (total_tokens["output"] / 1_000_000) * 15
    print(f"Estimated cost: ${cost_input + cost_output:.2f}")

    if args.dry_run:
        print("\n(Dry run - no changes written to database)")


if __name__ == "__main__":
    main()
