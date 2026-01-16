-- Table for Wikipedia extracts for OneEarth ecoregions
-- Source: English Wikipedia via MediaWiki API

DROP TABLE IF EXISTS public.eco_wikitext;

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

COMMENT ON TABLE public.eco_wikitext IS 'Wikipedia extracts for 847 OneEarth ecoregions';
COMMENT ON COLUMN public.eco_wikitext.eco_id IS 'FK to gaz.Ecoregions2017.eco_id';
COMMENT ON COLUMN public.eco_wikitext.wiki_title IS 'Canonical Wikipedia article title';
COMMENT ON COLUMN public.eco_wikitext.wiki_url IS 'Full Wikipedia URL';
COMMENT ON COLUMN public.eco_wikitext.extract_text IS 'Plain text extract of article';
COMMENT ON COLUMN public.eco_wikitext.rev_timestamp IS 'Wikipedia revision timestamp';
COMMENT ON COLUMN public.eco_wikitext.revid IS 'Wikipedia revision ID';
COMMENT ON COLUMN public.eco_wikitext.harvested_at IS 'When this record was harvested';
COMMENT ON COLUMN public.eco_wikitext.source IS 'Source wiki (e.g., enwiki)';

-- Index for text search if needed later
CREATE INDEX eco_wikitext_text_idx ON public.eco_wikitext USING gin(to_tsvector('english', extract_text));
