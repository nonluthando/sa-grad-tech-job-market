# Project Scope Decision: Broader Technology Market

## Status

Adopted before Milestone 3.

## Decision

The product is now **South African Tech Job Market Intelligence**. Its primary
analytical population is all publicly advertised South African technology roles
collected from supported employer career pages. Graduate, internship and junior
roles remain a dedicated early-career lens rather than the only records included
in the market analysis.

The repository slug remains `sa-grad-tech-job-market` to preserve links and Git
history. The product title and analytical contract carry the new scope.

## Evidence that prompted the change

The verified Milestone 2B build produced:

- 267 canonical jobs across five employers;
- 72 South African jobs;
- 121 technology jobs;
- 45 South African technology jobs; and
- 2 explicitly early-career South African technology jobs.

The pipeline and classifiers were working as intended. The narrow result was
mainly caused by the timing and coverage of current employer vacancies: most
observed South African technology openings were senior or did not state a role
level. A graduate-only product would therefore underuse the available data and
produce unstable analysis whenever graduate programmes were closed.

## Revised research question

> What roles, skills, seniority levels, locations and working arrangements are
> South African technology employers hiring for, and what does that market imply
> for early-career candidates?

## Data-contract change

The canonical dataset now separates market scope from career stage:

| Field | Meaning |
|---|---|
| `is_target_market` | The posting is South African and technology-related |
| `is_early_career` | The role is classified as internship, graduate or junior |
| both flags are true | The posting belongs to the early-career market lens |

The quality report exposes both the broad market count and the early-career
subset. This prevents the small early-career sample from being mistaken for the
size of the entire observed technology market.

## Why this is the preferred trade-off

### Benefits

- Uses the 45-role South African technology sample rather than analysing only two
  vacancies.
- Produces useful company, city, seniority and workplace analysis immediately.
- Allows skills and requirements to be compared across career stages.
- Makes low early-career availability a measurable finding rather than a product
  failure.
- Reduces dependence on graduate-programme recruitment seasons.

### Costs and risks

- The project title is broader than the original repository name.
- Senior roles may dominate aggregate skill counts unless analysis is segmented.
- Findings still represent the supported employers, not the entire South African
  labour market.
- The early-career sample remains too small for strong standalone conclusions.

These risks will be handled through explicit filters, sample-size warnings and
clear source-coverage reporting.

## Scope boundaries retained

The MVP still covers:

- South African roles only for published market findings;
- technology-related roles only;
- public employer career pages and supported public ATS endpoints;
- explainable deterministic classifications; and
- aggregate market analysis rather than applicant profiling.

The MVP still excludes salary prediction, résumé matching, application
automation, protected-attribute inference and unrestricted scraping of every job
platform.

## Milestone implications

- **Milestone 3:** Analyse the broad South African technology market, with a
  dedicated early-career section and sample-size warnings.
- **Milestone 4:** Extract skills, qualifications and experience requirements,
  segmented by role family and seniority.
- **Milestone 5:** Build a dashboard with market overview, role comparison and
  Entry-Level Reality views.
