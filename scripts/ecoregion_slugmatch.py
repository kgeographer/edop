#!/usr/bin/env python3
"""
Match WWF/Ecoregions2017 eco_name values to OneEarth title/slug rows.

Inputs:
  - missing88.tsv (eco_id, eco_name, ...)
  - oneearth_slugs.tsv (title, slug)

Output:
  - missing88_matched.tsv (eco_id, eco_name, matched_title, matched_slug, match_type, score)

Requires:
  pip install pandas rapidfuzz
"""

import re
import unicodedata
import pandas as pd
from rapidfuzz import process, fuzz


MISSING_PATH = "misc/missing88.tsv"
SLUGS_PATH = "misc/oneearth_slugs.tsv"
OUT_PATH = "misc/missing88_matched.tsv"


def strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def normalize(s: str) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = strip_diacritics(str(s)).lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[-–—/]", " ", s)
    s = re.sub(r"[(),.:;]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # common compound/spacing issues you noticed
    s = s.replace("rain forest", "rainforest").replace("rain forests", "rainforests")
    return s


# Extend this as you discover “renamed” / “alias” cases.
ALIASES = {
    "queen charlotte islands": "haida gwaii",
}


def apply_aliases(eco_name: str) -> str:
    s = normalize(eco_name)
    for k, v in ALIASES.items():
        if k in s:
            s = s.replace(k, v)
    return s


def build_index(slugs_df: pd.DataFrame):
    slugs_df = slugs_df.copy()
    slugs_df["norm"] = slugs_df["title"].apply(normalize)
    norm_titles = slugs_df["norm"].tolist()
    norm_to_title = dict(zip(slugs_df["norm"], slugs_df["title"]))
    norm_to_slug = dict(zip(slugs_df["norm"], slugs_df["slug"]))
    return norm_titles, norm_to_title, norm_to_slug


def match_one(eco_name: str, norm_titles, norm_to_title, norm_to_slug):
    n = apply_aliases(eco_name)

    # 1) exact normalized
    if n in norm_to_slug:
        return "exact_norm", 100.0, norm_to_title[n], norm_to_slug[n]

    # 2) exact after removing spaces (catches joined-compound quirks)
    n_nospace = n.replace(" ", "")
    nospace_map = {t.replace(" ", ""): t for t in norm_titles}
    if n_nospace in nospace_map:
        choice = nospace_map[n_nospace]
        return "exact_nospace", 100.0, norm_to_title[choice], norm_to_slug[choice]

    # 3) fuzzy: pick best across a few scorers
    candidates = []
    for scorer, label in [
        (fuzz.token_set_ratio, "token_set"),
        (fuzz.token_sort_ratio, "token_sort"),
        (fuzz.partial_ratio, "partial"),
    ]:
        choice, score, _ = process.extractOne(n, norm_titles, scorer=scorer)
        candidates.append((score, label, choice))

    score, label, choice = max(candidates, key=lambda x: x[0])

    # Conservative acceptance thresholds (tune as needed):
    # - token_set/token_sort >= 85 is usually safe
    # - partial >= 87 helps cases like “forests” vs “savanna-woodland”
    accept = (
        (label in {"token_set", "token_sort"} and score >= 85)
        or (label == "partial" and score >= 87)
    )

    if accept:
        return f"fuzzy_{label}", float(score), norm_to_title[choice], norm_to_slug[choice]

    return "unmatched", float(score), "", ""


def main():
    missing = pd.read_csv(MISSING_PATH, sep="\t")
    slugs = pd.read_csv(SLUGS_PATH, sep="\t")

    norm_titles, norm_to_title, norm_to_slug = build_index(slugs)

    rows = []
    for r in missing.itertuples(index=False):
        match_type, score, matched_title, matched_slug = match_one(
            r.eco_name, norm_titles, norm_to_title, norm_to_slug
        )
        rows.append(
            {
                "eco_id": r.eco_id,
                "eco_name": r.eco_name,
                "matched_title": matched_title,
                "matched_slug": matched_slug,
                "match_type": match_type,
                "score": score,
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(OUT_PATH, sep="\t", index=False)

    print("Total:", len(out))
    print("Matched:", (out["match_type"] != "unmatched").sum())
    print("Unmatched:", (out["match_type"] == "unmatched").sum())
    if (out["match_type"] == "unmatched").any():
        print("\nUnmatched rows:")
        print(out[out["match_type"] == "unmatched"][["eco_id", "eco_name", "score"]].to_string(index=False))


if __name__ == "__main__":
    main()