#!/usr/bin/env python3
import argparse
import json
from statistics import mean

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl_path", help="Path to wiki_extracts.jsonl")
    ap.add_argument("--show-empty", type=int, default=10, help="Show N examples with empty extract_text")
    args = ap.parse_args()

    total = 0
    has_text = 0
    empty_text = 0
    missing_key = 0
    parse_errors = 0

    lengths = []
    empty_examples = []

    with open(args.jsonl_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            if "extract_text" not in rec:
                missing_key += 1
                continue

            txt = rec.get("extract_text") or ""
            if txt.strip():
                has_text += 1
                lengths.append(len(txt))
            else:
                empty_text += 1
                if len(empty_examples) < args.show_empty:
                    empty_examples.append({
                        "line": line_no,
                        "eco_id": rec.get("eco_id"),
                        "eco_name": rec.get("eco_name"),
                        "wiki_title": rec.get("wiki_title"),
                        "pageid": rec.get("pageid"),
                        "fullurl": rec.get("fullurl"),
                        "resolved_via": rec.get("resolved_via"),
                        "match_score": rec.get("match_score"),
                    })

    print(f"Total JSONL records        : {total}")
    print(f"With non-empty extract_text: {has_text}")
    print(f"Empty extract_text         : {empty_text}")
    print(f"Missing extract_text key   : {missing_key}")
    print(f"JSON parse errors          : {parse_errors}")

    if lengths:
        print("\nText length stats (chars):")
        print(f"  min={min(lengths)}  avg={int(mean(lengths))}  max={max(lengths)}")

    if empty_examples:
        print(f"\nExamples with empty extract_text (up to {args.show_empty}):")
        for ex in empty_examples:
            print(f"- line {ex['line']}: eco_id={ex['eco_id']}  eco_name={ex['eco_name']!r}  "
                  f"wiki_title={ex['wiki_title']!r}  pageid={ex['pageid']}  resolved_via={ex['resolved_via']}")

if __name__ == "__main__":
    main()
