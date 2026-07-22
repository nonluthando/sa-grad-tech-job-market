# South African Graduate Tech Job Market Intelligence

An end-to-end analytics engineering project that collects public job postings,
builds a reliable job-market dataset, extracts role and skill requirements, and
publishes insights about South African graduate and junior technology hiring.

## Current status

**Milestone 1: Greenhouse raw ingestion**

Milestone 0 validated the current source candidates:

- Greenhouse Job Board API — primary source
- Lever Postings API — secondary source
- Discovery careers page — experimental SuccessFactors source
- Nedbank careers page — experimental SuccessFactors source
- Electrum careers page — experimental custom HTML source
- Prosple RSS — rejected for the MVP after a `403` response
- Adzuna API — deferred unless more coverage is required

The current production ingestion scope is deliberately narrower: Takealot Group,
Luno and Impact.com through Greenhouse's public Job Board API.

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Codespaces uses Bash, even when opened from an iPhone or Windows computer. In
Windows PowerShell outside Codespaces, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## Collect raw Greenhouse snapshots

```bash
python -m src.ingestion.collect
```

Collect one configured board:

```bash
python -m src.ingestion.collect --source-token takealotgroup
```

Generated snapshots are written beneath:

```text
data/raw/greenhouse/{board_token}/
```

Raw data is intentionally ignored by Git. Each snapshot includes an adjacent
metadata file with its UTC collection time, endpoint, job count and SHA-256 hash.
Identical responses are not written twice.

## Validate source coverage

```bash
python scripts/validate_sources.py
```

## Run tests

```bash
pytest
```

See:

- [`docs/data-source-assessment.md`](docs/data-source-assessment.md)
- [`docs/milestone-1-raw-ingestion.md`](docs/milestone-1-raw-ingestion.md)
