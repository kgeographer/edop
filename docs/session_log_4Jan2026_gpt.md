# EDOP Session Log — Wikipedia Text Exploration (ChatGPT)
**Date:** 04 January 2026

## Objective
Explore the feasibility of using Wikipedia textual descriptions as a semantic similarity signal for World Heritage (WH) sites, alongside the existing environmental PCA-based similarity framework in EDOP.

Initial focus was limited to the existing 20-site WH exemplar set, with an eye toward eventual corpus construction for the full WH catalog (~1,240 sites).

---

## Work Undertaken

### 1. Wikipedia Retrieval Strategy
- Chose to use the MediaWiki API rather than HTML scraping for robustness and reproducibility.
- Implemented a Python script (`fetch_wikipedia_wh.py`) to:
  - resolve canonical Wikipedia pages via search
  - retrieve pageid, canonical title, and full URL
  - fetch plain-text lead (intro) sections
- Added required `User-Agent` header to comply with Wikimedia API policy.

---

### 2. Lead Text Diagnostics
- Generated diagnostics for all 20 sites showing:
  - word counts
  - character counts
- Discovered substantial variance in lead length:
  - very short leads (e.g., Old Town of Lijiang, Iguazú National Park)
  - very long leads (e.g., Venice, Angkor, Göbekli Tepe)
- Concluded that **lead-only text is not uniformly suitable** as the basis for embeddings.

---

### 3. Section Structure Analysis
- Added a second API pass using `action=parse&prop=sections` to inventory article structure.
- Stored section metadata (index, title, level) as structured JSON (`wh_wikipedia_sections.json`) for inspection.
- Empirical finding:
  - 16 of 20 sites include a top-level section beginning with “History”
  - several include both “History” and “Historical overview”
- Confirmed that history-oriented sections are common but not universal.

---

### 4. History Section Retrieval
- Implemented logic to:
  - identify “history-like” sections programmatically (History*, Historical*)
  - retrieve section content using `action=parse&prop=wikitext`
- Combined lead text with retrieved history-section text to form provisional “documents”.

---

### 5. Corpus Construction & Normalization Issues
- Identified a core methodological problem:
  - mixing lead-only documents with lead+history documents introduces bias
  - naive truncation by “first N words” privileges editorial ordering rather than semantic importance
- Explicitly paused before generating embeddings in order to reason about:
  - what constitutes a comparable “place document”
  - how much text to include
  - how to normalize document length without obscuring meaning

---

## Current State
For each of the 20 exemplar WH sites, the pipeline now produces:
- canonical Wikipedia page resolution (title, pageid, URL)
- lead text (plain text)
- full section inventory (JSON)
- optional retrieval of history-section wikitext

No embeddings have been generated yet; this is a deliberate pause point.

---

## Next Steps (Near Term)
- Decide on a principled document construction strategy, e.g.:
  - lead + history with stratified or balanced truncation
  - fixed word budget split across discourse strata
  - percentile-based normalization rather than max-length truncation
- Generate normalized text documents for the 20 sites.
- Compute text-based similarity rankings and compare with environmental PCA similarity.

---

## Longer-Term Direction
- Generalize Wikipedia retrieval to all WH sites via Wikidata sitelinks.
- Store raw wikitext as canonical corpus material, with derived representations (lead, history, embeddings).
- Treat Wikipedia text as a distinct discursive layer complementary to EDOP’s environmental signatures.

---

## Session Close / Current Status

Following additional iteration and manual inspection, Wikipedia-derived text for all 20 exemplar World Heritage sites was cleaned of non-discursive markup and lightly normalized for length. The resulting file (`wh_wikipedia_leads.tsv`) contains narrative prose sufficient for embedding-based semantic similarity analysis, while retaining meaningful variation tied to site typology and editorial practice.

At this point, the Wikipedia text pipeline is considered complete for proof-of-concept purposes. The next step is to generate embeddings from the prepared text and expose text-based similarity measures alongside existing environmental PCA-based similarity in the EDOP interface.