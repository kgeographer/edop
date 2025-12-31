#!/usr/bin/env python3
"""
Parse OneEarth ecoregion links HTML and write a TSV: slug <tab> title

Input:  misc/one-earth-links.html
Output: misc/one-earth-link.tsv
"""

from __future__ import annotations

from pathlib import Path
import csv
import sys


def slug_from_href(href: str) -> str:
    # e.g. "/ecoregions/alps-conifer-and-mixed-forests/" -> "alps-conifer-and-mixed-forests"
    parts = [p for p in href.strip().split("/") if p]
    return parts[-1] if parts else ""


def main() -> int:
    in_path = Path("misc/one-earth-links.html")
    out_path = Path("misc/one-earth-link.tsv")

    if not in_path.exists():
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 2

    html = in_path.read_text(encoding="utf-8", errors="replace")

    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        print(
            "ERROR: BeautifulSoup is required.\n"
            "Install with: pip install beautifulsoup4\n",
            file=sys.stderr,
        )
        return 3

    soup = BeautifulSoup(html, "html.parser")

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    dupes: list[str] = []

    # Grab anchors that point into /ecoregions/ and have a <p> title somewhere inside
    for a in soup.select('a[href^="/ecoregions/"]'):
        href = a.get("href", "").strip()
        if not href:
            continue

        slug = slug_from_href(href)
        if not slug:
            continue

        p = a.find("p")
        if not p:
            continue

        title = p.get_text(strip=True)  # removes that leading space you noticed
        if not title:
            continue

        if slug in seen:
            dupes.append(slug)
            continue

        seen.add(slug)
        rows.append((slug, title))

    if not rows:
        print("WARNING: no rows extracted. Check input HTML structure.", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["slug", "title"])
        w.writerows(rows)

    if dupes:
        print(f"NOTE: skipped {len(dupes)} duplicate slug(s). Example: {dupes[:5]}", file=sys.stderr)

    print(f"Wrote {len(rows)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
