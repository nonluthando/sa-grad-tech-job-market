# Milestone 2D — Fintech and Gaming Source Expansion

## Objective

Expand direct-employer coverage beyond Greenhouse, Lever and SAP
SuccessFactors without making the project dependent on a paid aggregator.

The milestone introduces three provider adapters:

| Employer | Public careers platform | Adapter |
|---|---|---|
| DigiOutsource | Workday Candidate Experience | `workday` |
| ACI Worldwide | Oracle Fusion Candidate Experience | `oracle_hcm` |
| BET Software | WordPress / WP Job Manager | `wp_job_manager` |

## Why these employers

All three are relevant to the South African technology market but use platforms
that were not previously represented in the pipeline. Supporting them improves
company and industry diversity while retaining direct source lineage.

DigiOutsource adds online gaming and platform-engineering roles. ACI Worldwide
adds payments and enterprise-fintech roles. BET Software adds locally advertised
software, data and operational technology vacancies.

## Architecture decision

The project continues to use one shared canonical dataset, but each public
career platform has its own ingestion and transformation adapter.

```text
public provider endpoint
        |
        v
provider-specific collector
        |
        +--> exact listing responses
        +--> exact detail responses
        +--> bundle metadata and SHA-256 hashes
                         |
                         v
              provider-specific parser
                         |
                         v
                  CanonicalJob
```

This avoids forcing structurally different providers through one fragile generic
scraper.

## Raw-data contract

Each new collector writes a JSON envelope containing:

- provider and source identifiers;
- public endpoint information;
- the advertised job count;
- every listing response as exact base64-encoded bytes;
- every job-detail response as exact base64-encoded bytes;
- SHA-256 hashes for each embedded response; and
- a deterministic job index connecting listing and detail records.

The outer bundle is also hashed and receives the same metadata sidecar used by
existing providers.

## Completeness safeguards

### Workday

The collector pages through the public CXS endpoint until the number of unique
`externalPath` records equals the reported `total`. A mismatch fails the run.

### Oracle HCM

The collector follows the public Candidate Experience requisition endpoint,
uses `totalResults` and `hasMore` when available, and rejects a final unique
requisition count that does not match the reported total.

### WP Job Manager

The collector reads `max_num_pages`, extracts unique job-detail links from every
AJAX result page, and then downloads each detail page. It fails if pagination
stops producing new records before completion.

## Transformation approach

The adapters map provider-specific fields into the existing canonical schema and
then reuse the common explainable classifiers for:

- South African location evidence;
- workplace type;
- role seniority;
- technology relevance;
- early-career status; and
- target-market membership.

No provider is allowed to change the meaning of the common flags:

```text
is_target_market = South African technology role
is_early_career  = internship, graduate or junior evidence
```

## Trade-offs

### Benefits

- Broader direct-employer coverage without paid aggregation.
- Better industry diversity.
- Clear source lineage and reproducible raw snapshots.
- Provider failures remain isolated.
- The canonical analysis contract remains unchanged.

### Costs

- More provider-specific code and fixtures.
- Workday and Oracle endpoints may vary slightly by tenant configuration.
- The BET Software AJAX implementation is less standardised than the enterprise
  ATS APIs and therefore carries the highest live-validation risk.
- Detail-page collection is slower and creates more requests than compact APIs.

## Validation boundary

The implementation is considered code-complete when tests pass. Each source is
considered production-validated only after a complete live collection in
Codespaces confirms:

1. listing access succeeds;
2. pagination reaches the reported total;
3. every detail page is collected;
4. the raw bundle can be read back and hash-verified;
5. the canonical build succeeds; and
6. the quality report includes the provider and employer counts.

BET Software should remain marked experimental until its live AJAX response is
confirmed against the implemented WP Job Manager contract.

## Commands

```bash
python -m src.ingestion.collect --source-token digioutsource
python -m src.ingestion.collect --source-token aci-worldwide
python -m src.ingestion.collect --source-token betsoftware
python -m src.transformation.build
pytest -q
```

## Exit condition

Milestone 2D is complete when at least DigiOutsource and ACI Worldwide pass live
collection and transformation, while BET Software is either validated or kept
explicitly experimental with the observed incompatibility documented.
