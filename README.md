# South African Graduate Tech Job Market Intelligence

An end-to-end analytics engineering project that collects public job postings,
builds a reliable job-market dataset, extracts role and skill requirements, and
publishes insights about South African graduate and junior technology hiring.

## Current status

**Milestone 2 complete: cleaning and standardisation**

The project can now:

- collect exact raw Greenhouse snapshots from Takealot Group, Luno and Impact.com;
- verify raw-file integrity from metadata and SHA-256 hashes;
- clean HTML job descriptions into analysis-ready text;
- normalise South African locations and selected international countries;
- classify workplace type, role level and technology relevance;
- retain the evidence behind classifications;
- identify the target South African early-career technology market;
- deduplicate stable postings across collection snapshots;
- preserve first-seen, last-seen and observation history;
- write a schema-controlled Parquet dataset; and
- produce a data-quality report.

The latest verified Milestone 1 collection contained 100 raw jobs across the
three Greenhouse sources. Live counts change as employers publish and remove
vacancies.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Codespaces uses Bash. In Windows PowerShell outside Codespaces, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run the pipeline

### 1. Collect raw Greenhouse snapshots

```bash
python -m src.ingestion.collect
```

Collect one configured board:

```bash
python -m src.ingestion.collect --source-token takealotgroup
```

### 2. Build the canonical dataset

```bash
python -m src.transformation.build
```

Outputs:

```text
data/processed/
├── jobs.parquet
└── quality-report.json
```

`jobs.parquet` retains every standardised job and provides flags for South
African, technology and target-market roles. Jobs are not silently discarded
because a classification is uncertain.

### 3. Run tests

```bash
pytest
```

### 4. Validate source candidates

```bash
python scripts/validate_sources.py
```

## Pipeline architecture

```text
config/sources.json
        |
        v
Greenhouse collector
        |
        +--> exact raw JSON + metadata + SHA-256
                         |
                         v
             snapshot integrity checks
                         |
                         v
            cleaning and classifications
                         |
                         v
              stable-key deduplication
                         |
                         +--> data/processed/jobs.parquet
                         +--> data/processed/quality-report.json
```

## Repository structure

```text
.
├── config/
│   └── sources.json
├── data/
│   ├── raw/
│   ├── processed/
│   └── source-test-results/
├── docs/
│   ├── data-source-assessment.md
│   ├── milestone-1-raw-ingestion.md
│   └── milestone-2-cleaning.md
├── scripts/
│   └── validate_sources.py
├── src/
│   ├── ingestion/
│   └── transformation/
│       ├── build.py
│       ├── classification.py
│       ├── cleaning.py
│       ├── dataset.py
│       ├── greenhouse.py
│       ├── schema.py
│       └── snapshots.py
└── tests/
```

## Important design decisions

- **Raw data remains immutable.** Transformations never edit source snapshots.
- **No early destructive filtering.** The canonical dataset keeps all jobs and
  exposes classification flags.
- **Classifications are explainable.** Evidence is stored with each label.
- **Unknown is preferable to guessing.** Missing or ambiguous values remain
  unspecified and are visible in the quality report.
- **Deduplication is conservative.** Repeated Greenhouse IDs are merged across
  snapshots; fuzzy cross-company matching is deferred.
- **Parquet is the analytical contract.** Milestone 3 and later work will read
  the canonical file rather than reimplement raw parsing.

## MVP roadmap

| Milestone | Outcome | Status |
|---|---|---|
| 0. Source validation | Select viable public sources | Complete |
| 1. Raw ingestion | Preserve reproducible Greenhouse snapshots | Complete |
| 2. Cleaning and standardisation | Produce one canonical jobs dataset | Complete |
| 3. Skills extraction | Derive technologies and requirements | Next |
| 4. Analytics engine | Build market metrics and analysis tables | Planned |
| 5. Dashboard | Publish the interactive MVP | Planned |

## Documentation

- [Data-source assessment](docs/data-source-assessment.md)
- [Milestone 1: raw ingestion](docs/milestone-1-raw-ingestion.md)
- [Milestone 2: cleaning and standardisation](docs/milestone-2-cleaning.md)

## Responsible-use scope

The project collects only publicly advertised job information. It does not
submit applications, collect applicant data, bypass authentication, infer
protected personal attributes, or scrape platforms whose terms or access
controls make the intended collection inappropriate.
