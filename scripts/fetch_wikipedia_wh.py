#!/usr/bin/env python3
"""
Fetch Wikipedia lead text + canonical URL for selected World Heritage sites
using the MediaWiki API (no HTML scraping).

Output: TSV suitable for embeddings / Postgres import.
"""
import requests
import csv
import json
import time
import re
from pathlib import Path

HEADERS = {
    "User-Agent": "EDOP/0.1 (https://github.com/kgeographer/edop; contact: kgeographer)"
}
API = "https://en.wikipedia.org/w/api.php"

OUTFILE = Path("app/data/wh_wikipedia_leads.tsv")
SECTIONS_OUTFILE = Path("app/data/wh_wikipedia_sections.json")

# ---- Your 20 exemplar sites -----------------------------------------------

WH_SITES = [
    (668, "Angkor"),
    (198, "Cahokia Mounds State Historic Site"),
    (243, "Ellora Caves"),
    (1572, "Göbekli Tepe"),
    (158, "Head-Smashed-In Buffalo Jump"),
    (822, "Historic Centre (Old Town) of Tallinn"),
    (1033, "Historic Centre of Vienna"),
    (379, "Historic City of Toledo"),
    (688, "Historic Monuments of Ancient Kyoto (Kyoto, Uji and Otsu Cities)"),
    (274, "Historic Sanctuary of Machu Picchu"),
    (303, "Iguazu National Park"),
    (527, "Kyiv: Saint-Sophia Cathedral and Related Monastic Buildings, Kyiv-Pechersk Lavra"),
    (811, "Old Town of Lijiang"),
    (326, "Petra"),
    (603, "Samarkand – Crossroad of Cultures"),
    (880, "Summer Palace, an Imperial Garden in Beijing"),
    (492, "Taos Pueblo"),
    (119, "Timbuktu"),
    (447, "Uluru-Kata Tjuta National Park"),
    (394, "Venice and its Lagoon"),
]

# ---------------------------------------------------------------------------

def wiki_search(query: str):
    r = requests.get(API, params={
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 1,
        "format": "json",
        "utf8": 1,
    }, headers=HEADERS)
    r.raise_for_status()
    results = r.json()["query"]["search"]
    return results[0] if results else None


def wiki_page_extract(pageid: int):
    """
    Fetch lead/intro text (plain text) + canonical URL for a pageid.
    """
    params = {
        "action": "query",
        "pageids": pageid,
        "prop": "extracts|info",
        "explaintext": 1,
        "exintro": 1,
        "inprop": "url",
        "format": "json",
        "utf8": 1,
    }

    r = requests.get(API, params=params, headers=HEADERS)
    r.raise_for_status()
    page = r.json()["query"]["pages"][str(pageid)]
    return page

# def wiki_page_extract(pageid: int, expand: bool = False):
#     params = {
#         "action": "query",
#         "pageids": pageid,
#         "prop": "extracts|info",
#         "explaintext": 1,
#         "inprop": "url",
#         "format": "json",
#         "utf8": 1,
#     }
#
#     if expand:
#         params.update({
#             "exsectionformat": "plain",
#             "exlimit": 2
#         })
#     else:
#         params.update({
#             "exintro": 1
#         })
#
#     r = requests.get(API, params=params, headers=HEADERS)
#     r.raise_for_status()
#     page = r.json()["query"]["pages"][str(pageid)]
#     return page


# --- Section fetch helper
def wiki_sections(pageid: int):
    """
    Return list of section dicts for a page (MediaWiki action=parse).
    Each section dict typically includes: index, line (title), level, number, etc.
    """
    r = requests.get(API, params={
        "action": "parse",
        "pageid": pageid,
        "prop": "sections",
        "format": "json",
        "utf8": 1,
    }, headers=HEADERS)
    r.raise_for_status()
    return r.json().get("parse", {}).get("sections", []) or []

def select_history_section(sections):
    """
    Choose the best 'history-like' section index.
    Preference order:
      - title starts with 'History'
      - title starts with 'Historical'
    Returns section index as int, or None.
    """
    for s in sections:
        title = (s.get("line") or "").strip().lower()
        if title.startswith("history"):
            return int(s.get("index"))
    for s in sections:
        title = (s.get("line") or "").strip().lower()
        if title.startswith("historical"):
            return int(s.get("index"))
    return None


def html_to_text(html: str) -> str:
    """
    Lightweight HTML -> text for MediaWiki parse HTML.
    Good enough for embeddings; removes tags and collapses whitespace.
    """
    if not html:
        return ""
    html = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
    html = re.sub(r"(?i)<br\\s*/?>", " ", html)
    html = re.sub(r"(?i)</p>", " ", html)
    text = re.sub(r"(?s)<.*?>", " ", html)
    text = (text
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&lt;", "<")
            .replace("&gt;", ">"))
    return " ".join(text.split())


def fetch_section_text(pageid: int, section_index: int) -> str:
    """
    Fetch a specific section (by index) as parsed HTML, then strip to plain-ish text.
    """
    r = requests.get(API, params={
        "action": "parse",
        "pageid": pageid,
        "prop": "text",
        "section": section_index,
        "format": "json",
        "utf8": 1,
    }, headers=HEADERS)
    r.raise_for_status()
    html = r.json().get("parse", {}).get("text", {}).get("*", "") or ""
    return html_to_text(html)

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r", " ").replace("\n", " ")
    s = " ".join(s.split())
    return s


def main():
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    SECTIONS_OUTFILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTFILE.open("w", encoding="utf-8", newline="") as f_leads:
        writer = csv.writer(f_leads, delimiter="\t")

        sections_records = []
        lead_records = []
        lead_lengths = []

        for id_no, wh_name in WH_SITES:
            print(f"→ {wh_name}")

            search = wiki_search(wh_name)
            if not search:
                print(f"  ! No Wikipedia result")
                continue

            pageid = search["pageid"]
            page = wiki_page_extract(pageid)
            # page = wiki_page_extract(pageid, expand=False)

            wiki_title = page.get("title")
            wiki_url = page.get("fullurl")

            # Section inventory (helps diagnose whether pages have "History", stubs, etc.)
            try:
                sections = wiki_sections(pageid)
            except Exception as e:
                sections = []
                print(f"  ! Sections fetch failed: {e}")

            section_titles = " | ".join([s.get("line", "").strip() for s in sections if s.get("line")])
            sections_records.append({
                "id_no": id_no,
                "wh_name": wh_name,
                "wiki_title": wiki_title,
                "wiki_pageid": pageid,
                "wiki_url": wiki_url,
                "section_count": len(sections),
                "sections": [
                    {
                        "index": s.get("index"),
                        "number": s.get("number"),
                        "level": s.get("level"),
                        "title": s.get("line")
                    }
                    for s in sections
                ]
            })


            lead_text = page.get("extract", "") or ""
            lead_text_norm = normalize_text(lead_text)
            lead_len = len(lead_text_norm.split())
            lead_lengths.append(lead_len)

            # Try to fetch a history-like section for richer semantic signal
            history_text_norm = ""
            hist_index = select_history_section(sections)
            if hist_index is not None:
                try:
                    history_text_norm = normalize_text(fetch_section_text(pageid, hist_index))
                except Exception as e:
                    print(f"  ! History section fetch failed: {e}")
                    history_text_norm = ""

            combined = lead_text_norm
            if history_text_norm:
                combined = combined + " " + history_text_norm

            lead_records.append({
                "id_no": id_no,
                "wh_name": wh_name,
                "wiki_title": wiki_title,
                "wiki_pageid": pageid,
                "wiki_url": wiki_url,
                "combined_text": combined
            })

            # extract = page.get("extract", "") or ""
            # word_count = len(extract.split())
            #
            # # If lead is too short, refetch with first section included
            # if word_count < 120:
            #     page = wiki_page_extract(pageid, expand=True)
            #     extract = page.get("extract", "") or ""
            #     # keep only lead + first section
            #     parts = extract.split("\n\n")
            #     extract = "\n\n".join(parts[:2])
            #
            # wiki_lead = normalize_text(extract)
            #
            # writer.writerow([
            #     id_no,
            #     wh_name,
            #     wiki_title,
            #     pageid,
            #     wiki_url,
            #     wiki_lead
            # ])

            # Be polite to the API
            time.sleep(0.3)

        # Second pass: normalize all documents to a common word budget.
        # Budget is derived from the longest lead.
        max_lead_words = max(lead_lengths) if lead_lengths else 300

        f_leads.seek(0)
        f_leads.truncate()
        writer.writerow([
            "id_no",
            "wh_name",
            "wiki_title",
            "wiki_pageid",
            "wiki_url",
            "wiki_lead"
        ])

        for rec in lead_records:
            words = rec["combined_text"].split()
            truncated = " ".join(words[:max_lead_words])

            writer.writerow([
                rec["id_no"],
                rec["wh_name"],
                rec["wiki_title"],
                rec["wiki_pageid"],
                rec["wiki_url"],
                truncated
            ])

    with SECTIONS_OUTFILE.open("w", encoding="utf-8") as f:
        json.dump(sections_records, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {OUTFILE}")
    print(f"Wrote {SECTIONS_OUTFILE}")


if __name__ == "__main__":
    main()
