#!/usr/bin/env python3
"""
Build eco_id -> OneEarth slug lookup by matching eco_name to OneEarth title.

Inputs:
  - misc/eco847_names.tsv        (eco_id, eco_name)
  - misc/one-earth-link.tsv      (slug, title)

Outputs:
  - misc/eco847_oneearth_lookup.tsv
  - misc/eco847_oneearth_unmatched.tsv
  - misc/eco847_oneearth_ambiguous.tsv
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple


# --- config ---------------------------------------------------------------

AUTO_FUZZY_THRESHOLD = 0.94   # raise if you want fewer auto-accepted fuzzy matches
TOP_K_SUGGESTIONS = 5         # how many candidates to write for unmatched rows


# --- normalization --------------------------------------------------------

_dash_chars = {
    "\u2010",  # hyphen
    "\u2011",  # non-breaking hyphen
    "\u2012",  # figure dash
    "\u2013",  # en dash
    "\u2014",  # em dash
    "\u2212",  # minus sign
}

_punct_to_space_re = re.compile(r"[^a-z0-9]+", re.IGNORECASE)
_ws_re = re.compile(r"\s+")


def strip_diacritics(s: str) -> str:
    """
    Convert to NFKD and drop combining marks.
    'Bahía' -> 'Bahia'
    """
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_title(s: str) -> str:
    """
    Normalization intended for *matching*, not display.
    Rules (in order):
      - unicode normalize + strip diacritics
      - lowercase
      - unify various dash chars to "-"
      - "&" -> "and"
      - "rain forests" -> "rainforests" (whitespace-tolerant)
      - punctuation -> spaces
      - collapse whitespace
    """
    if s is None:
        return ""

    s = strip_diacritics(s)
    s = s.lower().strip()

    # unify dash-like chars
    for ch in _dash_chars:
        s = s.replace(ch, "-")

    # common token equivalences
    s = s.replace("&", "and")

    # collapse "rain forests" to "rainforests" (covers multiple spaces)
    s = re.sub(r"rain\s+forests", "rainforests", s)

    # punctuation -> space, collapse whitespace
    s = _punct_to_space_re.sub(" ", s)
    s = _ws_re.sub(" ", s).strip()
    return s


# --- i/o ------------------------------------------------------------------

@dataclass(frozen=True)
class OneEarthRow:
    slug: str
    title: str
    key: str


@dataclass(frozen=True)
class EcoRow:
    eco_id: int
    eco_name: str
    key: str


def read_oneearth(path: Path) -> List[OneEarthRow]:
    rows: List[OneEarthRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for r in rdr:
            slug = (r.get("slug") or "").strip()
            title = (r.get("title") or "").strip()
            if not slug or not title:
                continue
            rows.append(OneEarthRow(slug=slug, title=title, key=normalize_title(title)))
    return rows


def read_eco(path: Path) -> List[EcoRow]:
    rows: List[EcoRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for r in rdr:
            eco_id_raw = (r.get("eco_id") or "").strip()
            eco_name = (r.get("eco_name") or "").strip()
            if eco_id_raw == "" or eco_name == "":
                continue
            try:
                eco_id = int(eco_id_raw)
            except ValueError:
                continue
            rows.append(EcoRow(eco_id=eco_id, eco_name=eco_name, key=normalize_title(eco_name)))
    return rows


# --- matching -------------------------------------------------------------

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def build_index(oneearth: List[OneEarthRow]) -> Dict[str, List[OneEarthRow]]:
    idx: Dict[str, List[OneEarthRow]] = {}
    for r in oneearth:
        idx.setdefault(r.key, []).append(r)
    return idx


def top_suggestions(eco_key: str, oneearth: List[OneEarthRow], k: int = TOP_K_SUGGESTIONS) -> List[Tuple[float, OneEarthRow]]:
    scored = [(similarity(eco_key, r.key), r) for r in oneearth]
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:k]


# --- main -----------------------------------------------------------------

def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    eco_path = base_dir / "misc" / "eco847_names.tsv"
    oneearth_path = base_dir / "misc" / "one-earth-link.tsv"

    out_lookup = base_dir / "misc" / "eco847_oneearth_lookup.tsv"
    out_unmatched = base_dir / "misc" / "eco847_oneearth_unmatched.tsv"
    out_ambiguous = base_dir / "misc" / "eco847_oneearth_ambiguous.tsv"

    if not eco_path.exists():
        print(f"ERROR: missing input: {eco_path}", file=sys.stderr)
        return 2
    if not oneearth_path.exists():
        print(f"ERROR: missing input: {oneearth_path}", file=sys.stderr)
        return 2

    eco_rows = read_eco(eco_path)
    one_rows = read_oneearth(oneearth_path)
    one_idx = build_index(one_rows)

    matched: List[Tuple[EcoRow, OneEarthRow, str, float]] = []
    ambiguous: List[Tuple[EcoRow, List[OneEarthRow]]] = []
    unmatched: List[EcoRow] = []

    # 1) exact match on normalized key
    for e in eco_rows:
        candidates = one_idx.get(e.key, [])
        if len(candidates) == 1:
            matched.append((e, candidates[0], "norm_exact", 1.0))
        elif len(candidates) > 1:
            ambiguous.append((e, candidates))
        else:
            unmatched.append(e)

    # 2) for ambiguous keys, choose best by raw-title similarity (still deterministic)
    still_ambiguous: List[Tuple[EcoRow, List[OneEarthRow]]] = []
    for e, cands in ambiguous:
        # use normalized strings for tie-breaking, but compare against candidate titles too
        scored = [(similarity(normalize_title(e.eco_name), normalize_title(c.title)), c) for c in cands]
        scored.sort(key=lambda t: t[0], reverse=True)
        best_score, best = scored[0]
        # If the key is identical, score will be 1.0; otherwise keep it ambiguous
        if best_score >= 0.999:
            matched.append((e, best, "norm_exact_collision_resolved", best_score))
        else:
            still_ambiguous.append((e, cands))
    ambiguous = still_ambiguous

    # 3) fuzzy suggestions for remaining unmatched; auto-accept only above threshold
    still_unmatched: List[EcoRow] = []
    fuzzy_accepted: List[Tuple[EcoRow, OneEarthRow, str, float]] = []

    for e in unmatched:
        sugg = top_suggestions(e.key, one_rows, k=1)
        if not sugg:
            still_unmatched.append(e)
            continue
        score, best = sugg[0]
        if score >= AUTO_FUZZY_THRESHOLD:
            fuzzy_accepted.append((e, best, "fuzzy_auto", score))
        else:
            still_unmatched.append(e)

    matched.extend(fuzzy_accepted)

    # write lookup (importable)
    matched.sort(key=lambda t: t[0].eco_id)
    with out_lookup.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["eco_id", "eco_name", "slug", "oneearth_title", "match_type", "score"])
        for e, o, mtype, score in matched:
            w.writerow([e.eco_id, e.eco_name, o.slug, o.title, mtype, f"{score:.4f}"])

    # write ambiguous (for review)
    with out_ambiguous.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["eco_id", "eco_name", "eco_key", "candidate_slug", "candidate_title", "candidate_key"])
        for e, cands in ambiguous:
            for c in cands:
                w.writerow([e.eco_id, e.eco_name, e.key, c.slug, c.title, c.key])

    # write unmatched + top suggestions
    with out_unmatched.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["eco_id", "eco_name", "eco_key", "suggested_slug", "suggested_title", "suggested_key", "sim"])
        for e in sorted(still_unmatched, key=lambda x: x.eco_name.lower()):
            suggs = top_suggestions(e.key, one_rows, k=TOP_K_SUGGESTIONS)
            if not suggs:
                w.writerow([e.eco_id, e.eco_name, e.key, "", "", "", ""])
                continue
            for score, cand in suggs:
                w.writerow([e.eco_id, e.eco_name, e.key, cand.slug, cand.title, cand.key, f"{score:.4f}"])

    # summary
    eco_n = len(eco_rows)
    one_n = len(one_rows)
    matched_n = len(matched)
    print(f"Eco rows: {eco_n}")
    print(f"OneEarth rows: {one_n}")
    print(f"Matched: {matched_n}")
    print(f"Unmatched eco: {len(still_unmatched)}")
    print(f"Ambiguous eco: {len(ambiguous)}")
    print(f"Wrote: {out_lookup.relative_to(base_dir)}")
    print(f"Wrote: {out_unmatched.relative_to(base_dir)}")
    print(f"Wrote: {out_ambiguous.relative_to(base_dir)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())