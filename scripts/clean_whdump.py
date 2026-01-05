#!/usr/bin/env python3
import csv
import html
import re
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

def html_to_text(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    if not s:
        return ""

    # Unescape HTML entities first
    s = html.unescape(s)

    if BeautifulSoup:
        soup = BeautifulSoup(s, "html.parser")
        # Turn <p> into line breaks; keep text content
        text = soup.get_text("\n")
    else:
        # Fallback: crude tag strip
        text = re.sub(r"<[^>]+>", "", s)

    # Normalize whitespace but keep meaningful newlines
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return text

def clean_field(s: str) -> str:
    s = html_to_text(s)
    # IMPORTANT: remove literal newlines so TSV stays one-row-per-line
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", "\\n")   # escape newlines
    return s

def main(in_path: str, out_path: str):
    in_path = Path(in_path)
    out_path = Path(out_path)

    with in_path.open("r", encoding="utf-8", newline="") as f_in, \
         out_path.open("w", encoding="utf-8", newline="") as f_out:

        reader = csv.reader(f_in, delimiter="\t", quotechar='"', doublequote=True)
        writer = csv.writer(
            f_out,
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )

        for row in reader:
            cleaned = [clean_field(col) for col in row]
            writer.writerow(cleaned)

if __name__ == "__main__":
    # Example:
    # python scripts/clean_whdump.py app/data/world_heritage_2025.txt app/data/world_heritage_2025_clean.tsv
    import sys
    if len(sys.argv) != 3:
        print("Usage: clean_whdump.py <input.txt> <output.tsv>")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])