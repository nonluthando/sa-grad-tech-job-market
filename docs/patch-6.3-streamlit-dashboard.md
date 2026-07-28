# Patch 6.3 — Streamlit dashboard v1

## Purpose

Patch 6.3 turns the validated Patch 6.2 Parquet marts into an interactive portfolio dashboard. The UI does not collect, clean, classify or enrich vacancies. It reads only the final dashboard contract.

## Stack

- Streamlit for the web interface
- DuckDB for parameterised Parquet queries
- Plotly for interactive charts
- pandas for small filtered result frames
- Streamlit Community Cloud entry point at `streamlit_app.py`

## Views

1. **Overview** — vacancy volume, employers, role levels, activity and popular technologies.
2. **Employers** — employer and industry comparisons.
3. **Skills** — technologies, capabilities and a role-level heatmap.
4. **Early career** — graduate, internship and junior opportunity access.
5. **Locations & work** — province, city and remote/hybrid/office patterns.
6. **Opportunities** — a filtered vacancy table with application links.
7. **Data quality** — Patch 6.2 quality metrics, warnings and missing dimensions.

## Global filters

- Search term
- Employer
- Industry
- Province
- Work arrangement
- Role level
- Target-market-only switch
- Early-career-only switch
- Talent-pool exclusion

All filter values are passed to DuckDB as query parameters. SQL identifiers are selected only from fixed allowlists.

## Required data

The app requires:

```text
data/processed/dashboard_jobs.parquet
data/processed/dashboard_skills.parquet
data/processed/dashboard-quality-report.json
```

When these files are absent, the app stops with clear build instructions instead of showing invented demo data.

## Local run

```bash
uv pip install -r requirements.txt
uv run python -m src.transformation.build
uv run python -m src.skills.build
uv run python -m src.analytics.build
uv run streamlit run streamlit_app.py
```

## Streamlit Community Cloud

Deploy the repository and select `streamlit_app.py` as the entry point. The three dashboard output files must exist in the deployed branch.

## Tests

The patch adds unit tests for:

- Parameterised global filters
- Jobs-versus-skills search behaviour
- Missing input handling
- Quality-report validation
- Filter normalisation
- DuckDB-to-Parquet integration
- Plotly chart construction

## GitHub-only refresh

The manual **Refresh dashboard data** workflow is included for users who do not have a local terminal. From the repository's Actions tab, run the workflow to collect public listings, build all three data layers, run the test suite, upload the marts as an artifact and commit the three dashboard files back to the current branch.

Provider collection failures are reported as warnings. The workflow proceeds only when the successful snapshots are sufficient to build and validate the marts.
