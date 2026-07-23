# South African Tech Job Market Intelligence

An end-to-end analytics engineering project that collects public job postings,
builds a reliable job-market dataset, and publishes evidence about technology
hiring in South Africa. Graduate and junior opportunities remain a dedicated
early-career lens within the broader market.

## Current status

**Milestone 2D implemented: fintech and gaming source adapters**

The project can now:

- collect exact raw Greenhouse snapshots from Takealot Group, Luno and Impact.com;
- collect exact raw Lever snapshots from Mama Money and Yassir;
- collect paginated SAP SuccessFactors listings and job-detail pages from Discovery and Nedbank;
- collect Workday CXS listings and details from DigiOutsource;
- collect Oracle Candidate Experience requisitions from ACI Worldwide;
- collect WP Job Manager listing and detail pages from BET Software;
- verify raw-file integrity from metadata and SHA-256 hashes;
- clean HTML job descriptions into analysis-ready text;
- normalise South African locations and selected international countries;
- classify workplace type, role level and technology relevance;
- retain source-tagged evidence behind role-level classifications;
- use explicit Lever workplace and level fields when available;
- identify the target South African technology market;
- flag explicitly early-career roles as a separate analytical lens;
- deduplicate stable postings across collection snapshots;
- preserve first-seen, last-seen and observation history;
- write a schema-controlled Parquet dataset; and
- produce a data-quality report.

The latest verified Milestone 2C build contained 407 canonical jobs across seven
employers, including 71 South African technology roles and four explicitly
early-career roles. Milestone 2D adds three provider adapters; their live counts
will be recorded only after each collector passes a complete Codespaces run.

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

### 1. Collect raw job-board snapshots

```bash
python -m src.ingestion.collect
```

Collect one configured source:

```bash
python -m src.ingestion.collect --source-token takealotgroup
python -m src.ingestion.collect --source-token discovery
python -m src.ingestion.collect --source-token digioutsource
```

Page-based collectors follow every result page and then download each job detail.
They are intentionally slower than the compact Greenhouse and Lever feeds, and
all enforce completeness limits to avoid silently truncated datasets.

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

`jobs.parquet` retains every standardised job. `is_target_market` identifies
South African technology roles, while `is_early_career` identifies internship,
graduate and junior roles. Combining both flags produces the early-career
market lens without discarding broader hiring evidence.

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
Greenhouse + Lever + SuccessFactors + Workday + Oracle + WP collectors
        |
        +--> exact raw JSON or HTML bundle + metadata + SHA-256
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
│   ├── milestone-2-cleaning.md
│   ├── milestone-2b-quality-and-coverage.md
│   ├── milestone-2c-successfactors-sources.md
│   ├── milestone-2d-fintech-gaming-sources.md
│   └── project-scope.md
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
│       ├── lever.py
│       ├── successfactors.py
│       ├── workday.py
│       ├── oracle_hcm.py
│       ├── wp_job_manager.py
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
- **Deduplication is conservative.** Repeated provider job IDs are merged across
  snapshots; fuzzy cross-company matching is deferred.
- **Parquet is the analytical contract.** Milestone 3 and later work will read
  the canonical file rather than reimplement raw parsing.
- **Early career is a lens, not a destructive filter.** The main analysis covers
  all South African technology roles and reports graduate and junior evidence
  separately.

## MVP roadmap

| Milestone | Outcome | Status |
|---|---|---|
| 0. Source validation | Select viable public sources | Complete |
| 1. Raw ingestion | Preserve reproducible Greenhouse snapshots | Complete |
| 2. Cleaning and standardisation | Produce one canonical jobs dataset | Complete |
| 2B. Quality and source coverage | Add Lever and strengthen level evidence | Complete |
| 2C. Direct-employer expansion | Add Discovery and Nedbank SuccessFactors sites | Complete |
| 2D. Fintech and gaming coverage | Add DigiOutsource, ACI Worldwide and BET Software adapters | Implemented; live validation next |
| 3. Baseline market analysis | Answer core market questions | Next |
| 4. Skills extraction | Derive technologies and requirements | Planned |
| 5. Dashboard | Publish the interactive MVP | Planned |

## Documentation

- [Data-source assessment](docs/data-source-assessment.md)
- [Milestone 1: raw ingestion](docs/milestone-1-raw-ingestion.md)
- [Milestone 2: cleaning and standardisation](docs/milestone-2-cleaning.md)
- [Milestone 2B: quality and source coverage](docs/milestone-2b-quality-and-coverage.md)
- [Milestone 2C: SuccessFactors source expansion](docs/milestone-2c-successfactors-sources.md)
- [Milestone 2D: fintech and gaming sources](docs/milestone-2d-fintech-gaming-sources.md)
- [Project scope decision](docs/project-scope.md)

## Responsible-use scope

The project collects only publicly advertised job information. It does not
submit applications, collect applicant data, bypass authentication, infer
protected personal attributes, or scrape platforms whose terms or access
controls make the intended collection inappropriate.
