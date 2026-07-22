# South African Graduate Tech Job Market Intelligence

An end-to-end analytics engineering project that collects public job postings,
builds a historical job-market dataset, extracts role and skill requirements,
and publishes insights about South African graduate and junior technology hiring.

## Current status

**Milestone 0: Source validation**

The first source candidates are:

- Greenhouse Job Board API — primary candidate
- Lever Postings API — secondary candidate
- Prosple RSS — deferred until later validation
- Adzuna API — deferred unless additional market coverage is needed

## Run the source validation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run:

```bash
python scripts/validate_sources.py
```

The script writes a timestamped result to:

```text
data/source-test-results/
```

Run the tests:

```bash
pytest
```

## Milestone 0 exit criteria

Milestone 0 passes when at least one source:

1. returns a successful structured response;
2. contains at least one South African vacancy;
3. exposes a stable source job ID;
4. includes a title, location, description and application URL;
5. can be queried repeatedly without authentication; and
6. has a documented public access method suitable for a portfolio project.

See [`docs/data-source-assessment.md`](docs/data-source-assessment.md).
