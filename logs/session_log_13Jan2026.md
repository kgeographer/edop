# Session Log: 13 January 2026

## Objective
First production deployment of EDOP to Digital Ocean droplet (edop.kgeographer.org).

---

## 1. Database Export Strategy

### Required Tables Identified
Analyzed `app/` code to identify tables needed for the app to run:

**Public schema (22 tables + 1 view):**
- `basin08` - 190k sub-basins with geometry and cluster_id
- `basin08_pca` - pgvector table (50-dim PCA vectors)
- `basin08_pca_clusters` - cluster assignments by hybas_id
- `v_basin08_persist` - view joining basin08 with lookups
- 10 lookup tables: `lu_cls`, `lu_clz`, `lu_fec`, `lu_fmh`, `lu_glc`, `lu_lit`, `lu_pnv`, `lu_tbi`, `lu_tec`, `lu_wet`
- WH sites tables: `edop_wh_sites`, `edop_clusters`, `edop_similarity`, `edop_text_similarity`, `edop_text_clusters`
- WH cities tables: `whc_clusters`, `whc_similarity`, `whc_band_similarity`, `whc_band_clusters`, `whc_band_summaries`

**Gaz schema (2 tables):**
- `gaz.wh_cities` - 258 World Heritage cities
- `gaz.edop_gaz` - 97k gazetteer places

### Deployment Scripts Created
- `misc/dump_for_deploy.sh` - exports tables to `/tmp/edop_dumps/`
- `misc/restore_on_droplet.sh` - restores on server with dependency ordering

### Export Process
```bash
./misc/dump_for_deploy.sh
# Creates 6 SQL files totaling ~1.4GB
# Compressed to 511MB tarball
```

---

## 2. Database Schema Fixes

### Foreign Key Migration
Result tables had FKs pointing to `public.wh_cities` but canonical table is `gaz.wh_cities`.

**Fixed locally:**
```sql
-- Drop old FKs (9 constraints across whc_* tables)
ALTER TABLE whc_band_clusters DROP CONSTRAINT whc_band_clusters_city_id_fkey;
-- ... etc

-- Add PK to gaz.wh_cities (was missing)
ALTER TABLE gaz.wh_cities ADD PRIMARY KEY (id);

-- Recreate FKs pointing to gaz schema
ALTER TABLE whc_band_clusters ADD CONSTRAINT whc_band_clusters_city_id_fkey
  FOREIGN KEY (city_id) REFERENCES gaz.wh_cities(id);
-- ... etc

-- Drop redundant table
DROP TABLE public.wh_cities;
```

### Re-exported affected tables
```bash
pg_dump --clean --if-exists -t ... > 02_result_tables.sql
pg_dump --clean --if-exists -t gaz.wh_cities -t gaz.edop_gaz > 05_gaz_schema.sql
```

---

## 3. Server Configuration Issues

### PostgreSQL Port Mismatch
- Local dev: PostgreSQL on port **5435**
- Server: PostgreSQL on standard port **5432**
- App defaults to 5435 when no env var set

**Solution:** Set `PGPORT=5432` in server environment.

### Environment Variable Names
Initial `.env` file used wrong variable names:
```
# WRONG
DB_PORT=5432
DB_HOST=localhost

# CORRECT (PostgreSQL standard)
PGPORT=5432
PGHOST=localhost
```

### Systemd EnvironmentFile Issues
Multiple problems getting systemd to load environment:
1. Service file was corrupted (contained shell heredoc syntax literally)
2. EnvironmentFile permissions prevented reading
3. Ultimately used inline `Environment=` directives:

```ini
[Service]
Environment="PGHOST=localhost"
Environment="PGPORT=5432"
Environment="PGDATABASE=edop"
Environment="PGUSER=postgres"
Environment="WHG_API_TOKEN=..."
```

### PostgreSQL Authentication
Server required password auth (unlike local peer auth):
```bash
# Changed pg_hba.conf: md5 → trust for 127.0.0.1
sudo systemctl restart postgresql
```

---

## 4. Missing Data Issues

### basin08.cluster_id Column
The `basin08` table on server predated clustering work. Column existed but was empty.

**Fix:**
```sql
ALTER TABLE basin08 ADD COLUMN IF NOT EXISTS cluster_id INTEGER;
UPDATE basin08 b SET cluster_id = c.cluster_id
FROM basin08_pca_clusters c WHERE c.hybas_id = b.hybas_id;
CREATE INDEX IF NOT EXISTS idx_basin08_cluster_id ON basin08(cluster_id);
```

### pg_trgm Extension
Required for trigram index on `gaz.edop_gaz.title`:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 5. Frontend Bug Fix

### Broken Variable Reference
After converting country dropdown to autocomplete, leftover code referenced old `whgCountrySelect` variable.

**Error:** `Uncaught ReferenceError: whgCountrySelect is not defined`

**Fix:** Removed dead code and added re-search triggers to new handlers:
- `addCountry()` - re-searches when country added
- Tag removal handler - re-searches when country removed
- Reset filter handler - re-searches when filters cleared

---

## 6. Final Deployment Steps

```bash
# Local: commit and push
git add -A
git commit -m "Fix country filter re-search + add deployment scripts"
git push origin whgapi
git checkout main
git merge whgapi
git push origin main

# Server: pull and restart
cd /var/www/edop
git fetch origin
git checkout main
git pull origin main
sudo systemctl restart edop
```

---

## Files Created/Modified

```
misc/dump_for_deploy.sh      # Database export script
misc/restore_on_droplet.sh   # Database restore script
app/templates/index.html     # Fixed whgCountrySelect bug
docs/session_log_13Jan2026.md  # This file
```

---

## Deployment Checklist (for future reference)

1. **Database**
   - [ ] All required tables exported (`dump_for_deploy.sh`)
   - [ ] Extensions installed: `postgis`, `vector`, `pg_trgm`
   - [ ] Schema `gaz` created
   - [ ] Tables loaded in dependency order
   - [ ] View `v_basin08_persist` created after tables
   - [ ] `basin08.cluster_id` populated from `basin08_pca_clusters`

2. **Environment**
   - [ ] `.env` or systemd Environment with correct variable names (`PGHOST`, `PGPORT`, etc.)
   - [ ] `PGPORT=5432` (not 5435)
   - [ ] `WHG_API_TOKEN` set

3. **PostgreSQL**
   - [ ] `pg_hba.conf` allows app connections (trust or password)
   - [ ] Service restarted after config changes

4. **Application**
   - [ ] Latest code pulled from main branch
   - [ ] `systemctl restart edop`
   - [ ] Hard browser refresh to clear cached JS

---

## Notes

- First production deployment of EDOP
- Domain: edop.kgeographer.org
- Server: Digital Ocean droplet via nginx reverse proxy to gunicorn:8001
- Total database size: ~1.4GB uncompressed, ~500MB compressed
