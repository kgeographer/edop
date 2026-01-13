#!/bin/bash
# EDOP Database Export for Deployment
# Run this locally to create dump files for the Digital Ocean droplet
#
# Usage: ./misc/dump_for_deploy.sh
#
# Creates files in misc/dumps/ directory

set -e

# Database connection (local)
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5435}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-edop}"

DUMP_DIR="/tmp/edop_dumps"
mkdir -p "$DUMP_DIR"

echo "=== EDOP Database Export ==="
echo "Source: $PGUSER@$PGHOST:$PGPORT/$PGDATABASE"
echo "Output: $DUMP_DIR/"
echo ""

# 1. Small lookup tables (lu_*)
echo "[1/5] Dumping lookup tables..."
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --no-owner --no-acl \
  -t lu_cls -t lu_clz -t lu_fec -t lu_fmh -t lu_glc \
  -t lu_lit -t lu_pnv -t lu_tbi -t lu_tec -t lu_wet \
  > "$DUMP_DIR/01_lookup_tables.sql"
echo "   -> 01_lookup_tables.sql ($(du -h "$DUMP_DIR/01_lookup_tables.sql" | cut -f1))"

# 2. Result/analysis tables (small)
echo "[2/5] Dumping result tables..."
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --no-owner --no-acl \
  -t edop_wh_sites -t edop_clusters -t edop_similarity \
  -t edop_text_similarity -t edop_text_clusters \
  -t whc_clusters -t whc_similarity \
  -t whc_band_similarity -t whc_band_clusters -t whc_band_summaries \
  > "$DUMP_DIR/02_result_tables.sql"
echo "   -> 02_result_tables.sql ($(du -h "$DUMP_DIR/02_result_tables.sql" | cut -f1))"

# 3. basin08 (large - 190k rows with geometry)
echo "[3/5] Dumping basin08 (this may take a minute)..."
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --no-owner --no-acl \
  -t basin08 \
  > "$DUMP_DIR/03_basin08.sql"
echo "   -> 03_basin08.sql ($(du -h "$DUMP_DIR/03_basin08.sql" | cut -f1))"

# 4. basin08_pca (pgvector table)
echo "[4/5] Dumping basin08_pca (pgvector)..."
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --no-owner --no-acl \
  -t basin08_pca \
  > "$DUMP_DIR/04_basin08_pca.sql"
echo "   -> 04_basin08_pca.sql ($(du -h "$DUMP_DIR/04_basin08_pca.sql" | cut -f1))"

# 5. gaz schema tables
echo "[5/5] Dumping gaz schema..."
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --no-owner --no-acl \
  -t gaz.wh_cities -t gaz.edop_gaz \
  > "$DUMP_DIR/05_gaz_schema.sql"
echo "   -> 05_gaz_schema.sql ($(du -h "$DUMP_DIR/05_gaz_schema.sql" | cut -f1))"

# 6. View definition (extract from database)
echo "[+] Extracting view definition..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c "
SELECT pg_get_viewdef('v_basin08_persist'::regclass, true);
" | sed 's/^/  /' > "$DUMP_DIR/06_view_definition.sql.tmp"

# Wrap in CREATE VIEW statement
cat > "$DUMP_DIR/06_view_definition.sql" << 'HEADER'
-- View: v_basin08_persist
-- Must be created AFTER basin08 and all lu_* tables are loaded

DROP VIEW IF EXISTS v_basin08_persist;
CREATE VIEW v_basin08_persist AS
HEADER
cat "$DUMP_DIR/06_view_definition.sql.tmp" >> "$DUMP_DIR/06_view_definition.sql"
echo ";" >> "$DUMP_DIR/06_view_definition.sql"
rm "$DUMP_DIR/06_view_definition.sql.tmp"
echo "   -> 06_view_definition.sql"

echo ""
echo "=== Export Complete ==="
echo ""
ls -lh "$DUMP_DIR"/*.sql
echo ""
echo "Next steps:"
echo "  1. scp $DUMP_DIR/*.sql karlg@kgeographer.org:/home/karlg/xfer/"
echo "  2. On droplet: ./restore_on_droplet.sh /home/karlg/xfer"
