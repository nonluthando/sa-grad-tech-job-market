# Milestone 2C — Direct-employer SuccessFactors expansion

## Purpose

The broader South African technology-market scope needs more employer coverage
before baseline analysis. The project therefore adds two large direct-employer
career sites that use SAP SuccessFactors:

- Discovery
- Nedbank

The sources remain first-party employer pages. No aggregator is introduced into
the production dataset.

## Why these sources

The source-validation phase had already confirmed that both sites expose
server-rendered, paginated vacancy lists with stable `/job/.../{id}/` detail
links. They add substantial South African coverage and include software, data,
quality engineering, platform and related technology roles.

Electrum remains experimental. Its current careers site contains valuable
programme information, but it does not expose the same stable, general vacancy
listing contract as the two SuccessFactors portals.

## Collection contract

SuccessFactors does not provide the same simple public JSON endpoint used by
Greenhouse or Lever. The collector therefore:

1. downloads the first listing page;
2. reads the advertised `Results x-y of z` total;
3. follows deterministic offset pages until every unique job link is found;
4. fails if pagination stops early or the reported total changes mid-run;
5. downloads every discovered job-detail page;
6. stores the exact response bytes for every listing and detail page inside one
   base64-encoded JSON bundle; and
7. writes normal snapshot metadata and SHA-256 integrity information.

The bundle is intentionally verbose. It preserves source evidence so parsing can
be improved later without re-requesting pages that may have changed or closed.

## Transformation contract

The snapshot reader verifies:

- the outer raw-file SHA-256 hash;
- every embedded listing-page hash;
- every embedded job-detail-page hash;
- the reported job total;
- the number of saved detail pages; and
- the metadata `source_job_count`.

Only after those checks does it parse each job into the canonical schema.

The detail parser uses SuccessFactors-specific selectors with conservative
fallbacks for:

- job title;
- location;
- posting date;
- description; and
- numeric source job ID.

The normal location, workplace, role-level and technology classifiers then run
unchanged. `is_target_market` continues to mean a South African technology role,
while `is_early_career` remains the separate graduate/junior/internship lens.

## Responsible collection controls

- Requests identify the project through a clear user agent.
- A configurable delay is applied before each detail-page request.
- Pagination has a configured maximum-page guard.
- Partial collections fail instead of being published as complete.
- The collector accesses only public vacancy pages and does not submit forms,
  authenticate, or bypass access controls.

## Trade-offs

### Benefits

- first-party provenance;
- wider South African employer coverage;
- full descriptions for later skills extraction;
- stable numeric job identifiers;
- auditable raw evidence; and
- no paid API dependency.

### Costs

- many more HTTP requests than JSON APIs;
- slower collection;
- greater sensitivity to HTML-template changes; and
- larger raw snapshots because page bytes are preserved.

The trade-off is acceptable because the two sites materially improve coverage
while preserving direct employer lineage.

## Verification

Run one source independently first:

```bash
python -m src.ingestion.collect --source-token discovery
python -m src.ingestion.collect --source-token nedbank
```

Then rebuild the combined dataset:

```bash
python -m src.transformation.build
cat data/processed/quality-report.json
```

The quality report should include `successfactors` in
`provider_job_counts`, and Discovery and Nedbank in the company breakdown.

## Exit condition

Milestone 2C is complete when:

- both complete public listings are collected;
- no completeness or integrity checks fail;
- canonical jobs are produced from both sources;
- the provider and company counts reconcile; and
- the full automated test suite passes.
