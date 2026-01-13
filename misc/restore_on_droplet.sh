#!/bin/bash
# EDOP Database Restore for Digital Ocean Droplet
# Run this on the remote server after scp'ing dump files
#
# Usage: ./restore_on_droplet.sh [dump_directory]
#
# Prerequisites:
#   - PostgreSQL with PostGIS extension
#   - pgvector extension available
#   - Database 'edop' created
#   - gaz schema created

set -e

# Database connection (remote)
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-edop}"

DUMP_DIR="${1:-.}"

echo "=== EDOP Database Restore ==="
echo "Target: $PGUSER@$PGHOST:$PGPORT/$PGDATABASE"
echo "Source: $DUMP_DIR/"
echo ""

# Function to run SQL file with error handling
run_sql() {
  local file="$1"
  local desc="$2"

  if [ ! -f "$file" ]; then
    echo "   SKIP: $file not found"
    return 1
  fi

  echo -n "   Loading $desc... "
  if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
      -v ON_ERROR_STOP=1 -q -f "$file" 2>/dev/null; then
    echo "OK"
    return 0
  else
    echo "FAILED"
    return 1
  fi
}

# Check prerequisites
echo "[0/7] Checking prerequisites..."

# Check PostGIS
echo -n "   PostGIS: "
if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
    "SELECT 1 FROM pg_extension WHERE extname='postgis'" 2>/dev/null | grep -q 1; then
  echo "OK"
else
  echo "MISSING - installing..."
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "CREATE EXTENSION IF NOT EXISTS postgis;"
fi

# Check pgvector
echo -n "   pgvector: "
if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
    "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>/dev/null | grep -q 1; then
  echo "OK"
else
  echo "MISSING - installing..."
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "CREATE EXTENSION IF NOT EXISTS vector;"
fi

# Check/create gaz schema
echo -n "   gaz schema: "
if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
    "SELECT 1 FROM information_schema.schemata WHERE schema_name='gaz'" 2>/dev/null | grep -q 1; then
  echo "OK"
else
  echo "MISSING - creating..."
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "CREATE SCHEMA IF NOT EXISTS gaz;"
fi

echo ""

# Load in dependency order
echo "[1/6] Lookup tables (lu_*)..."
run_sql "$DUMP_DIR/01_lookup_tables.sql" "10 lookup tables"

echo "[2/6] Result tables..."
run_sql "$DUMP_DIR/02_result_tables.sql" "WH sites + cities analysis tables"

echo "[3/6] basin08 (large table - please wait)..."
run_sql "$DUMP_DIR/03_basin08.sql" "190k basin geometries"

echo "[4/6] basin08_pca (pgvector)..."
run_sql "$DUMP_DIR/04_basin08_pca.sql" "PCA vectors for similarity"

echo "[5/6] gaz schema tables..."
run_sql "$DUMP_DIR/05_gaz_schema.sql" "wh_cities + edop_gaz"

echo "[6/6] Creating view..."
run_sql "$DUMP_DIR/06_view_definition.sql" "v_basin08_persist view"

echo ""
echo "=== Restore Complete ==="
echo ""

# Verify counts
echo "Verification:"
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" << 'EOF'
SELECT 'basin08' as table_name, count(*) as rows FROM basin08
UNION ALL SELECT 'basin08_pca', count(*) FROM basin08_pca
UNION ALL SELECT 'gaz.wh_cities', count(*) FROM gaz.wh_cities
UNION ALL SELECT 'gaz.edop_gaz', count(*) FROM gaz.edop_gaz
UNION ALL SELECT 'edop_wh_sites', count(*) FROM edop_wh_sites
UNION ALL SELECT 'lu_tec (ecoregions)', count(*) FROM lu_tec
ORDER BY 1;
EOF

echo ""
echo "Test the app at your domain to verify everything works."
