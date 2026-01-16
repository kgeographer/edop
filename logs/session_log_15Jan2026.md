# Session Log: 15 January 2026

## Objective
Harvest Wikipedia text extracts for 847 OneEarth ecoregions and persist to database.

---

## 1. Wikipedia API Issue Diagnosis

### Problem
Existing scripts (`harvest_ecoregion_wikipedia.py`, `refetch_wiki_extracts.py`) were only retrieving extracts for ~15 of 847 ecoregions despite Wikipedia pages existing for most.

### Root Cause
MediaWiki's extracts API has an `exlimit` restriction: when requesting full article text (`explaintext=1` without `exintro=1`), **only 1 page per request** is allowed. The scripts were batching 50 titles but silently receiving only 1 extract per batch.

**API warning revealed the issue:**
```json
{
  "warnings": {
    "extracts": {
      "warnings": "\"exlimit\" was too large for a whole article extracts request, lowered to 1."
    }
  }
}
```

### Solution
Rewrote `refetch_wiki_extracts.py` to fetch one title at a time. With 0.2s delay, 847 titles takes ~3 minutes — well within Wikipedia API etiquette guidelines.

---

## 2. Database Table: `public.eco_wikitext`

Created table to persist Wikipedia extracts for ecoregions.

**Schema:**
```sql
CREATE TABLE public.eco_wikitext (
    eco_id        BIGINT PRIMARY KEY REFERENCES gaz."Ecoregions2017"(eco_id),
    wiki_title    TEXT NOT NULL,
    wiki_url      TEXT,
    extract_text  TEXT,
    rev_timestamp TIMESTAMPTZ,
    revid         BIGINT,
    harvested_at  TIMESTAMPTZ DEFAULT now(),
    source        TEXT DEFAULT 'enwiki'
);

-- Full-text search index
CREATE INDEX eco_wikitext_text_idx ON public.eco_wikitext
    USING gin(to_tsvector('english', extract_text));
```

**Loader script:** `scripts/load_eco_wikitext.py`
- Reads JSONL from harvest scripts
- Parses ISO timestamps from Wikipedia
- Upserts with `ON CONFLICT` for idempotent reloads

**Result:** 751/847 ecoregions loaded (88.5% coverage)

---

## 3. Triage of Missing 96 Ecoregions

### Automated Triage
Created `scripts/triage_missing_ecoregions.py` to find potential Wikipedia matches:
1. Check if exact title exists or redirects
2. Search Wikipedia for candidates
3. Fuzzy match using `rapidfuzz.token_set_ratio`
4. Categorize results

### Results

| Category | Count | Description |
|----------|-------|-------------|
| strong_match | 7 | High-confidence matches (score ≥85) |
| partial_match | 19 | Possible matches, need review (score 60-85) |
| redirect | 45 | Exact title redirects to related article |
| no_match | 25 | No good Wikipedia candidates found |

### Observations
- **Redirects (45)** are most promising — spelling variants like "Belizian pine savannas" → "Belizean pine forests"
- **Strong matches** include false positives — 5 Antarctic tundra regions redirect to generic "Tundra" article
- **No match (25)** are mostly Antarctic regions and newer ecoregions (2017→2023 dataset growth)

### Review File
Fetched extracts for all 71 non-"no_match" candidates.

**Output:** `output/missing_for_review_with_extracts.tsv`

**Columns:** eco_id, eco_name, status, best_title, best_url, score, redirected_from, candidates, notes, extract_len, extract_preview

---

## 4. Manual Review and Final Load

### Review Process
Manual review of 71 candidates in spreadsheet:
- Added `accept` column (y/blank)
- Added `section` column for 4 cases where content exists in a section of a broader article
- Verified URLs, corrected a few erroneous matches
- Added `best_title` column for direct API queries

### Review Decisions

| Decision | Count |
|----------|-------|
| Accepted (full article) | 66 |
| Accepted (section extract) | 4 |
| Rejected (false positive) | 1 |

**Section extracts:**
- Transantarctic Mountains tundra → "Antarctic" section in Tundra article
- Northwest Antarctic Peninsula tundra → "Arctic" section in Tundra article
- Rapa Nui and Sala y Gómez subtropical forests → "Geography; Ecology" sections in Easter Island article
- Appalachian Piedmont forests → "Piedmont province" section in Appalachian Highlands article

**Rejected:**
- Gariep Karoo → matched to "Gariep Arts Festival" (false positive)

### Fetch Script
Created `scripts/fetch_reviewed_extracts.py`:
- Reads reviewed TSV with accept/section columns
- Fetches full extracts for accepted rows
- Fetches specific sections using `action=parse&section=N` for section cases
- Converts wikitext to plain text for section extracts
- Outputs JSONL for database loading

### Final Result

| Metric | Value |
|--------|-------|
| Total ecoregions | 847 |
| With Wikipedia text | 821 |
| Coverage | **96.9%** |
| Missing | 26 |

**Missing 26:** Mostly Antarctic tundra regions and newer ecoregions without dedicated Wikipedia articles.

---

## Files Created/Modified

```
sql/eco_wikitext.sql                          # Table DDL
scripts/refetch_wiki_extracts.py              # Fixed to fetch one title at a time
scripts/load_eco_wikitext.py                  # JSONL → database loader
scripts/triage_missing_ecoregions.py          # Automated triage for missing ecoregions
scripts/fetch_review_extracts.py              # Fetch extract previews for review
scripts/fetch_reviewed_extracts.py            # Fetch full extracts for accepted candidates
output/missing_triage.tsv                     # Full triage results (96 rows)
output/missing_for_review.tsv                 # Non-no_match candidates (71 rows)
output/missing_for_review_with_extracts.tsv   # With extract previews for manual review
output/missing_wiki_reviewed.tsv              # Manual review decisions
output/reviewed_extracts.jsonl                # Final 70 accepted extracts
```

---

## Notes

- MediaWiki API `exlimit` restriction is documented but easy to miss — batched requests silently return partial data
- 0.2s delay between requests is conservative; Wikipedia allows much higher rates for identified bots
- Claude Code diagnosed the API issue in minutes after 90 minutes of unsuccessful ChatGPT debugging
