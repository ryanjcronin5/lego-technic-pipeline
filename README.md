# Technic Insights

[![CI](https://github.com/ryanjcronin5/lego-technic-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanjcronin5/lego-technic-pipeline/actions/workflows/ci.yml)

An automated data pipeline and analytics API over the full LEGO catalogue (~25k sets), focused on **LEGO Technic**. It downloads the public [Rebrickable](https://rebrickable.com/downloads/) data dumps on a schedule, validates and transforms them, loads them into Postgres (or SQLite) and serves the results through a FastAPI backend and a small dashboard.

Questions it answers:

- How has the average Technic set size grown since 1977, compared with LEGO as a whole?
- Which Technic sets are the biggest?
- Which parts turn up most across Technic sets?
- **Which sets are most similar to one I own?** Sets are ranked by Jaccard similarity over the part types they share.

## Architecture

```mermaid
flowchart LR
    R[Rebrickable CSV dumps] -->|extract: cached download| E[raw .csv.gz]
    E -->|schema contract check| T[transform: pandas]
    T -->|quality gates| L[load: one transaction]
    L --> DB[(Postgres / SQLite)]
    DB --> API[FastAPI]
    API --> UI[Dashboard]
    GH[GitHub Actions nightly cron] -.-> E
```

| Stage | What happens |
|---|---|
| **Extract** ([extract.py](src/technic/extract.py)) | Downloads 6 dumps with a local cache and atomic writes, then checks that every column the pipeline depends on exists. If Rebrickable changes its format, the run fails loudly instead of producing silently wrong data. |
| **Transform** ([transform.py](src/technic/transform.py)) | Walks the theme tree to tag every Technic sub-theme, keeps only the latest inventory version per set, drops spare parts and merges duplicates. Quality gates check for unique keys, positive quantities and orphan rows. |
| **Load** ([load.py](src/technic/load.py)) | Replaces all data tables in one transaction, so the API never sees a half-finished load, and records each run in `pipeline_runs`. |
| **Serve** ([api.py](src/technic/api.py), [analytics.py](src/technic/analytics.py)) | Portable SQL that runs unchanged on SQLite and Postgres, typed Pydantic responses, auto-generated OpenAPI docs at `/docs`, and a 503 with a helpful message when no data has been loaded. |

## Quick start

### Local (SQLite)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
technic-etl                # download (~16 MB) and load into data/technic.db, ~30 s
uvicorn technic.api:app --reload
```

Open http://localhost:8000 for the dashboard, or http://localhost:8000/docs for the API.

To try it offline with the small test dataset: `technic-etl --source tests/fixtures`.

### Docker (Postgres)

```bash
docker compose up -d --build        # Postgres + API
docker compose run --rm etl         # run the pipeline once
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/summary` | Headline counts and when the data was last refreshed |
| `GET /api/trends` | Per year: Technic set count, plus average parts for Technic vs all sets |
| `GET /api/sets/biggest?limit=10` | Largest Technic sets |
| `GET /api/sets/search?q=bugatti` | Search Technic sets by name or number |
| `GET /api/sets/{set_num}` | Set details |
| `GET /api/sets/{set_num}/similar` | Most similar sets by shared part types |
| `GET /api/compare?a=42083-1&b=42115-1` | Overlap between two sets, with shared parts |
| `GET /api/parts/top` | Most-used parts across Technic |

## Testing and CI

```bash
pytest                                  # SQLite
TEST_DATABASE_URL=postgresql+psycopg://technic:technic@localhost:5432/technic pytest  # Postgres
ruff check . && ruff format --check .
```

- **[CI](.github/workflows/ci.yml)**: lint, then the test suite against both SQLite and a Postgres service container, then a Docker build with a smoke test.
- **[Nightly refresh](.github/workflows/nightly.yml)**: runs the real pipeline against live Rebrickable data, posts a run summary and uploads the database as an artifact. It also acts as an upstream data-contract monitor.

The tests use a small hand-built dataset in [tests/fixtures](tests/fixtures) with known answers. It covers nested sub-themes, superseded inventory versions, spare parts and multi-colour parts.

## Configuration

Set these as environment variables (see [.env.example](.env.example)): `DATABASE_URL`, `RAW_DIR`, `REBRICKABLE_BASE_URL`, `FOCUS_THEME` (any top-level theme works, e.g. `--theme "Star Wars"`) and `MAX_CACHE_AGE_HOURS`.

## Credits

Data comes from [Rebrickable](https://rebrickable.com/). LEGO® is a trademark of the LEGO Group, which does not sponsor, authorise or endorse this project.
