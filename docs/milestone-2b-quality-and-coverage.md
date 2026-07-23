# Milestone 2B: Classification Quality and Source Coverage

## Status

Implemented. Run the live collector and dataset build to produce current counts.

## Why this pass was needed

Milestone 2 successfully produced 100 canonical records, but only one record met
all three target-market conditions: South African, technology-related and
explicitly early-career.

A manual diagnostic showed that most senior classifications were supported by
real title evidence such as `Senior`, `Lead`, `Principal` and `Manager`. The
larger issue was coverage: the first production dataset only contained three
Greenhouse employers, and many relevant engineering titles did not explicitly
state a level.

Milestone 2B therefore improves both source coverage and classification
traceability without weakening the conservative target-market definition.

## Added source coverage

The production collector now supports the public Lever Postings API as well as
Greenhouse. The two already validated Lever sources are enabled:

- Mama Money
- Yassir

The collector preserves the exact JSON response bytes, writes the same metadata
and SHA-256 integrity fields used for Greenhouse, and stores snapshots beneath:

```text
data/raw/
├── greenhouse/<board-token>/
└── lever/<site-token>/
```

### Lever completeness guard

The MVP requests one large Lever page so that the exact HTTP response remains
the raw-data contract. If the response reaches the configured page limit, the
collector fails rather than silently treating a possibly truncated page as a
complete source snapshot.

The default limit is 500 and can be changed with:

```bash
python -m src.ingestion.collect --lever-page-limit 500
```

Full multi-page raw-response storage can be added later if a source grows beyond
this boundary.

## Lever transformation mapping

Lever records are mapped into the existing canonical schema:

| Lever field | Canonical field |
|---|---|
| `id` | `source_job_id` |
| `text` | `title` |
| `categories.location` / `allLocations` | `location_raw` |
| `categories.department` / `team` | `department` / `office` |
| `descriptionPlain`, `lists`, `additionalPlain` | `description_text` |
| `applyUrl` or `hostedUrl` | `application_url` |
| `workplaceType` | `workplace_type` |
| `categories.level`, when present | role-level evidence |
| `country` | location-country evidence |

Lever does not provide a public posting-updated timestamp in the same way as
Greenhouse. `source_updated_at` therefore remains null for Lever records rather
than creating a misleading timestamp.

## Role-level quality changes

### Senior title evidence is authoritative

The following title terms are evaluated before any early-career evidence:

- Senior
- Staff
- Principal
- Lead
- Manager
- Director
- Head of
- Architect
- Vice President / VP
- Chief

This prevents a title such as `Graduate Programme Manager` from being
incorrectly downgraded because the description or title also contains
`graduate`.

### Stronger early-career description evidence

When the title does not specify a level, the classifier can use explicit phrases
such as:

- recent, new or fresh graduate;
- entry-level or early-career role;
- 0–1, 0–2 or 1–2 years of experience;
- up to two years of experience;
- less than two years of experience;
- one year of professional experience; and
- no prior or professional experience required.

The classifier remains conservative. A plain title such as `Software Engineer`
is not automatically labelled junior merely because it lacks a senior keyword.

### Evidence provenance

`role_level_evidence` now identifies where the evidence came from, for example:

```text
title: Senior
description: 0-2 years of professional experience
source_level: Associate
```

This makes quality reviews possible without rereading every full description.

## Explicit Lever fields

When Lever provides an explicit workplace type, it takes precedence over loose
mentions of remote work elsewhere in the description. Supported values are
normalised to:

- `hybrid`
- `remote`
- `on_site`
- `unspecified`

An explicit Lever level can support a role-level classification, but it cannot
override a senior title.

## Updated quality report

The report now includes:

- canonical job counts by provider;
- South African technology-job count;
- role-level distribution within South African technology jobs;
- number of jobs carrying role-level evidence; and
- target-market counts by company.

These fields make the next source-coverage decision visible before analysis is
published.

## Run order

```bash
python -m src.ingestion.collect
python -m src.transformation.build
pytest -q
cat data/processed/quality-report.json
```

Existing duplicate snapshots may be reported as `DUPLICATE`; that is expected.
New Lever directories should appear beneath `data/raw/lever` after the first
successful collection.

## Acceptance checks

Milestone 2B is accepted when:

1. Greenhouse and Lever sources collect without silent truncation;
2. snapshot hashes and job counts validate;
3. the canonical dataset contains both providers;
4. senior titles remain senior despite early-career description text;
5. explicit early-career evidence is stored with its provenance;
6. all tests pass; and
7. the quality report provides enough detail to judge whether the sample is
   ready for baseline market analysis.

## Subsequent scope decision

Milestone 2B was designed while the target market still meant South African,
technology-related and explicitly early-career. The live build later produced
45 South African technology roles but only 2 explicitly early-career roles.

Before Milestone 3, the product scope was broadened. `is_target_market` now
means all South African technology roles, and `is_early_career` preserves the
original graduate and junior lens. The historical motivation and classification
work in this document remain valid; the new semantics are documented in
[`project-scope.md`](project-scope.md).

## Next milestone

Milestone 3 is baseline market analysis. It will use the canonical Parquet file
to answer core questions about companies, locations, workplace types, role
levels and role families before detailed skill extraction is added in Milestone
4.
