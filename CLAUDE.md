# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EDOP (Environmental Dimensions of Place) is a Python/FastAPI web application that provides environmental analytics for spatial humanities research. It exposes global physical geographic and climatic data from the BasinATLAS dataset as normalized "environmental signatures" for any geographic location.

## Tech Stack

- **Backend**: FastAPI 0.1, Python 3.10+
- **Database**: PostgreSQL 12+ with PostGIS extension
- **Frontend**: Vanilla JavaScript, Bootstrap 5.3.3, Leaflet 1.9.4 (CDN)
- **Package Manager**: pip

## Running the Application

```bash
# Install dependencies
pip install fastapi uvicorn psycopg[binary] python-dotenv certifi

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

## Environment Variables

Create a `.env` file with:
```
PGHOST=localhost
PGPORT=5435
PGDATABASE=edop
PGUSER=postgres
PGPASSWORD=
WHG_API_TOKEN=<token>
```

## Database Setup

Run SQL scripts in order:
```bash
psql -h localhost -p 5435 -U postgres -d edop < sql/basin_atlas_08.sql
psql -h localhost -p 5435 -U postgres -d edop < sql/ecoregion_view.sql
psql -h localhost -p 5435 -U postgres -d edop < sql/overrides.sql
```

## Architecture

```
app/
├── main.py           # FastAPI app init, mounts routers and static files
├── settings.py       # Loads .env, exposes WHG_API_TOKEN
├── api/routes.py     # REST endpoints (/api/signature, /api/resolve, etc.)
├── db/signature.py   # Core data logic: PostgreSQL queries, elevation APIs, profile formatting
├── web/pages.py      # Jinja2 template routes (GET /)
├── templates/        # HTML templates (base.html, index.html)
└── static/           # CSS, JS, vendor assets
```

### Key Data Flow

1. User inputs coordinates, place name, or selects World Heritage site
2. Backend queries PostgreSQL with PostGIS `ST_Covers()` for basin containing point
3. External APIs (OpenTopoData → Open-Meteo fallback) provide point elevation
4. Response includes 47+ BasinATLAS fields organized into profile_summary and profile_groups (A-D categories)

### API Endpoints

- `GET /api/health` - Health check
- `GET /api/signature?lat=X&lon=Y` - Returns environmental signature for coordinates
- `GET /api/resolve?name=X` - Place name resolution via WHG API
- `GET /api/wh-sites` - Returns 20 World Heritage seed sites

## Testing

```bash
# Health check
curl http://localhost:8000/api/health

# Signature for Timbuktu (canonical test coordinate)
curl "http://localhost:8000/api/signature?lat=16.76618535&lon=-3.00777252"

# Place resolution
curl "http://localhost:8000/api/resolve?name=Timbuktu"
```

## Key Files

- **app/db/signature.py** (440 lines): Core signature query logic, elevation API integration, profile grouping. Uses psycopg3 for database connections.
- **app/templates/index.html** (677 lines): Main UI with 3-tab layout (Main, Compare, World Heritage) and Leaflet map
- **app/static/js/main.js** (670 lines): Client-side logic for map, forms, API calls
- **metadata/*.tsv**: 11 lookup tables for decoding categorical field IDs to labels

## External APIs

- **WHG (World Historical Gazetteer)**: Place resolution, uses WHG_API_TOKEN
- **OpenTopoData**: Point elevation (Mapzen 30m DEM)
- **Open-Meteo**: Fallback elevation (Copernicus GLO-90)

## Notes

- Timbuktu coordinates (16.76618535, -3.00777252) are the canonical test location
- WHG API calls happen server-side only; token never sent to browser
- Elevation cache is in-process LRU (512 entries), lost on restart
- Static files mount requires running from project root
