# Milestone 0 — Data Source Assessment

**Project:** South African Graduate Tech Job Market Intelligence  
**Assessment date:** 22 July 2026  
**Status:** In progress — Greenhouse and Lever selected for live validation; Prosple deferred.

## Goal

Identify at least one structured, refreshable source that returns real South African
technology vacancies and provides enough information for later role, experience,
qualification and skill extraction.

## Evaluation criteria

Each source is evaluated on:

- public and documented access;
- structured response format;
- stable job identifiers;
- description completeness;
- location coverage;
- refreshability;
- historical snapshot suitability;
- maintenance risk;
- access or publication restrictions.

## Source matrix

| Source | Access method | Authentication | Structured data | SA evidence | Main limitations | Decision |
|---|---|---:|---:|---:|---|---|
| Greenhouse | Public Job Board API | No for GET | JSON | Takealot, Luno and Impact.com expose South African boards/roles | Employer-by-employer collection; no universal discovery endpoint | **Primary** |
| Lever | Public Postings API | No | JSON | Mama Money and Yassir expose Cape Town/Johannesburg/South Africa roles | Employer-by-employer collection; fields vary by employer | **Secondary** |
| Prosple | RSS when enabled; partner GraphQL access | Unknown for ZA RSS | RSS/GraphQL | South African directory exists | ZA RSS availability not yet confirmed | Deferred |
| Adzuna | Registered API | API key | JSON | Coverage still needs measurement | Quotas, attribution and publication/licensing considerations | Deferred |

## Greenhouse assessment

Official endpoint contract:

```text
GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
```

Expected useful fields:

- `id`
- `internal_job_id`
- `title`
- `updated_at`
- `location.name`
- `absolute_url`
- `content`
- `departments`
- `offices`

### Candidate boards

| Company | Board token | Why it is useful |
|---|---|---|
| Takealot Group | `takealotgroup` | South African employer with software, data, analytics and junior/graduate opportunities |
| Luno | `luno` | South African engineering, data, security and operations roles; useful for historical snapshots |
| Impact.com | `impact` | Cape Town data, software, product and technical-services roles |

### Assessment

Greenhouse is the strongest first source because the public GET endpoint requires no
authentication, returns stable posting identifiers and can include the full job description.
It also gives us multiple South African employers with relevant technology roles.

## Lever assessment

Official endpoint contract:

```text
GET https://api.lever.co/v0/postings/{site}?mode=json
```

Expected useful fields:

- `id`
- `text`
- `categories`
- `country`
- `descriptionPlain`
- `lists`
- `hostedUrl`
- `applyUrl`
- `workplaceType`
- optional salary fields

### Candidate boards

| Company | Lever site | Why it is useful |
|---|---|---|
| Mama Money | `mamamoney` | Cape Town and South African fintech roles across data and software |
| Yassir | `Yassir` | Includes Johannesburg, Cape Town and Pretoria among its location options and has Product/Tech roles |

### Assessment

Lever is suitable as the second adapter. Its plaintext description fields and explicit
workplace type are especially useful. We should not add it to the production ingestion
until the Greenhouse adapter and raw-data contract are stable.

## Scope controls

The project will collect only publicly advertised job information. It will not:

- submit applications;
- collect applicant or candidate data;
- bypass authentication or anti-bot controls;
- scrape LinkedIn, Indeed, PNet or OfferZen;
- infer protected personal attributes;
- republish complete job descriptions as a competing job board.

The analytical dataset will preserve source URLs and collection timestamps. Public-facing
outputs should present derived statistics and short evidence excerpts rather than reproducing
entire adverts.

## Initial decision

1. Implement **Greenhouse first**.
2. Validate Takealot Group, Luno and Impact.com.
3. Keep **Lever** as the second adapter, beginning with Mama Money.
4. Revisit Prosple only after the baseline pipeline works.
5. Evaluate Adzuna only if employer-specific sources do not provide enough coverage.

## Milestone 0 pass condition

The included validation script records whether each source returns:

- HTTP success;
- parseable JSON;
- unique IDs;
- complete required fields;
- South African locations; and
- technology-role candidates.

Milestone 0 is complete when the saved validation result shows at least one passing source
and the chosen source is recorded here with the observed counts and test timestamp.
