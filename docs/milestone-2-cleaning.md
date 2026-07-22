# Milestone 2: Cleaning and Standardisation

## Status

Complete.

## Goal

Turn immutable Greenhouse snapshots into one deterministic, analysis-ready
Parquet dataset without changing or deleting the raw source data.

## Command

```bash
python -m src.transformation.build
```

The command reads all Greenhouse metadata sidecars beneath `data/raw`, verifies
each raw file, transforms every job observation, deduplicates repeated postings
across snapshots and writes:

```text
data/processed/
├── jobs.parquet
└── quality-report.json
```

Use alternative directories when testing or rebuilding historical data:

```bash
python -m src.transformation.build \
  --raw-root /tmp/job-market-raw \
  --output-root /tmp/job-market-processed
```

## Transformation boundary

The raw layer remains authoritative. The transformation layer may read raw JSON
and metadata, but it never edits snapshots.

```text
raw metadata + exact raw JSON
              |
              v
    integrity verification
              |
              v
 text and field standardisation
              |
              v
 explainable classification
              |
              v
 stable-key deduplication
              |
              v
 Parquet + quality report
```

## Canonical record

Each Parquet row represents the latest known observation of one stable
Greenhouse posting and retains its history and lineage.

### Identity and lineage

- `job_key`
- `source_provider`
- `source_name`
- `source_token`
- `source_job_id`
- `source_snapshot_sha256`
- `source_snapshot_path`
- `first_seen_at`
- `last_seen_at`
- `source_updated_at`
- `observation_count`

### Clean job fields

- `title`
- `title_normalized`
- `company`
- `department`
- `office`
- `description_text`
- `application_url`

### Location and market fields

- `location_raw`
- `city`
- `province`
- `country`
- `location_evidence`
- `is_south_africa`
- `workplace_type`

### Role classifications

- `role_level`
- `role_level_evidence`
- `is_technology_role`
- `technology_evidence`
- `is_target_market`

### Data quality

- `data_quality_issues`

Missing optional values do not cause a posting to disappear. The row is retained
and the issue is recorded.

## Text cleaning

Greenhouse descriptions can contain HTML, HTML entities and inconsistent
whitespace. The cleaner:

1. decodes escaped entities;
2. extracts visible text;
3. excludes script and style contents; and
4. collapses whitespace.

The original HTML remains available in the raw snapshot.

## Location rules

South African city aliases are normalised to canonical city and province names.
Examples include:

- `CPT`, `Capetown` and `Cape Town` -> Cape Town, Western Cape;
- `JHB`, `Sandton` and `Johannesburg` -> Johannesburg, Gauteng;
- `PTA` and `Pretoria` -> Pretoria, Gauteng; and
- `DBN`, `Umhlanga` and `Durban` -> Durban, KwaZulu-Natal.

Remote roles are marked as South African only when the location or description
contains explicit South African evidence. The pipeline does not infer a city for
an advert that only says `Remote`.

## Workplace classification

The output labels are:

- `hybrid`
- `remote`
- `on_site`
- `unspecified`

Hybrid has precedence when an advert mentions both hybrid and remote work.

## Role-level classification

The output labels are:

- `internship`
- `graduate`
- `junior`
- `senior`
- `unspecified`

Title evidence is considered first. Explicit description phrases such as
`graduate programme`, `entry-level role` and `0-2 years` are used only when the
title does not already provide a level.

## Technology-role classification

Technology classifications use governed title and department patterns for areas
such as:

- software development;
- data and analytics;
- AI and machine learning;
- cloud, DevOps and platform engineering;
- cybersecurity;
- QA and test engineering;
- business intelligence and systems analysis; and
- technology product roles.

Known false positives such as `Data Protection Officer`, `Data Capturer` and
`Software Sales` are excluded. Generic graduate titles can use description
evidence, but ordinary non-technical titles are not classified from incidental
technology words in their descriptions.

A posting is marked `is_target_market = true` only when it is:

1. explicitly South African;
2. classified as a technology role; and
3. classified as internship, graduate or junior.

The full canonical dataset still retains jobs that do not meet those conditions.
This prevents early filtering from hiding classification mistakes.

## Deduplication decision

The stable key uses the provider, board token and Greenhouse job ID. When an ID
is unavailable, the application URL is hashed; content-based identity is the
last fallback.

Repeated observations of the same posting are collapsed into one row containing:

- the latest observed job fields;
- first and last collection timestamps; and
- the number of observations.

Milestone 2 deliberately does not use fuzzy cross-company matching. Similar job
titles at different employers are not evidence that two adverts are duplicates.

## Quality report

`quality-report.json` records:

- snapshot and observation counts;
- canonical and duplicate counts;
- South African, technology and target-market counts;
- company, role-level and workplace distributions; and
- counts of recorded data-quality issues.

## Failure behaviour

The build fails rather than silently trusting a snapshot when:

- required metadata is absent;
- collection time is invalid;
- the raw file is missing;
- the SHA-256 hash does not match;
- the JSON does not contain a jobs list; or
- the metadata job count differs from the raw list.

## Testing

Tests cover:

- HTML and entity cleaning;
- location, workplace, level and technology rules;
- known false positives;
- canonical Greenhouse transformation;
- missing-field quality flags;
- raw snapshot integrity checks;
- repeat-observation deduplication;
- quality-report metrics; and
- real Parquet writing when `pyarrow` is installed.
