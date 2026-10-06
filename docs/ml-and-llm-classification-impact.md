# Impact: scikit-learn and Gemini classification layers

This records what the two optional suggestion layers — the scikit-learn
second-stage role-level classifier and the Gemini-assisted classifier —
actually add on top of the deterministic pipeline, measured against the
live dataset (`data/processed/jobs.parquet`: 1,661 jobs, 196 target-market)
rather than estimated. For the design and the precedence rules both layers
sit on top of, see
[`docs/role-classification-engine.md`](role-classification-engine.md). For
the correctness work that preceded both additions, see
[`docs/regex-classification-audit.md`](regex-classification-audit.md).

## The gap, before either layer existed

Of the 196 target-market jobs, the deterministic rules alone leave:

| Field | Unresolved | % of target market |
|---|---|---|
| `role_level` | 89 | 45% |
| `workplace_type` | 116 | 59% |
| `city` (job is in South Africa but no city identified) | 13 | 7% |
| **At least one of the three** | **152** | **78%** |

`country`/`is_south_africa` are not in this table because both are already
100% resolved for every target-market job — there is nothing for either
suggestion layer to add there, which is why neither one attempts it.

## Layer 1: scikit-learn second-stage classifier

`scripts/train_role_classifier.py` trains a TF-IDF + logistic regression
model on the 934 jobs the deterministic rules already labelled with high
confidence (so it learns from the rules' clearest cases, not their
uncertainty), then suggests a `role_level` for the 89 jobs left
`unspecified`.

| Metric | Value |
|---|---|
| Training examples | 747 (187 held out as test) |
| Accuracy (held out) | 90.4% |
| Macro-F1 (held out) | 91.0% |
| Weakest class | `junior` recall: 61.3% |
| Jobs suggested | 89 — closes 100% of the `role_level` gap |

**Macro-F1, not accuracy, is the headline metric**, and that choice isn't
cosmetic: the training labels are heavily imbalanced (650 `senior` vs. 4
`mid_level` examples), so accuracy alone would hide the model's real
weak point — missing roughly 2 in 5 genuine `junior` postings. Reporting
per-class recall is what surfaced that weakness instead of hiding it
behind a reassuring 90% headline.

Output fields (`ml_suggested_role_level`, `ml_role_level_confidence`) are
written to a separate CSV and never merged into the canonical dataset.

## Layer 2: Gemini-assisted classifier

`scripts/classify_with_gemini.py` is the only layer that addresses
`workplace_type` and `city`, not just `role_level` — the deterministic
rules and the scikit-learn model both only ever produce a role-level
opinion. It targets the full 152-job gap (not just the 89 role-level
jobs), using Gemini's structured output (a Pydantic `response_schema`) so
parsing is reliable rather than scraped from free text. A job's suggestion
keeps only the fields that were actually unresolved for it — an opinion on
an already-confident field is discarded, never compared against or used to
override the canonical value.

Two real examples from an actual run, not synthetic test fixtures,
demonstrate the kind of inference regex and the scikit-learn model
structurally cannot make, because neither reads free text for context:

- **"Intermediate Software Engineer - GoLang"** -> suggested `mid_level`.
  The deterministic title rules have no `mid_level` category at all, so
  this job would otherwise stay `unspecified` indefinitely regardless of
  how it's worded.
- **"Senior Web Engineer"** -> suggested `workplace_type: hybrid`,
  reasoning from "we empower our people to choose where they would like to
  do their best work... we also encourage our teams to travel so we can
  make magic happen face to face." No regex pattern parses a qualifying
  clause like that.

Output fields (`llm_suggested_role_level`, `llm_suggested_workplace_type`,
`llm_suggested_city`, plus a confidence and one-line rationale per field)
are written to a separate CSV and never merged into the canonical dataset.

**Operational note**: the model this layer defaults to
(`gemini-3.1-flash-lite`) was chosen after `gemini-3.8-flash` proved
unreliable under real load (frequent transient 503 "high demand" errors
during testing) — the script retries with backoff regardless, but model
choice mattered more than retry logic for actually finishing a batch.

## Combined effect

| | Before | After |
|---|---|---|
| Target-market jobs with zero opinion on role level, workplace type, or city | 152 (78%) | 0 — every one has at least a suggestion from one or both layers |
| Role-level coverage, including suggestions | 107/196 resolved, 89 silent | 107/196 resolved + 89 ML-suggested (100% covered) |
| Workplace-type coverage, including suggestions | 80/196 resolved, 116 silent | 80/196 resolved + up to 116 Gemini-suggested |
| City coverage, including suggestions | 183/196 resolved, 13 silent | 183/196 resolved + up to 13 Gemini-suggested |
| Dashboard visibility | No way to see suggestion coverage or distribution | "AI-assisted suggestions" panel: 4 coverage metrics + 3 charts (ML role-level donut, Gemini role-level donut, Gemini workplace-type bar) in the Vacancies tab |

"Up to" reflects that both suggestion scripts are manually run and
API-rate-limited — actual coverage at any moment depends on when they were
last run, which is itself part of the design: these are deliberately
optional, re-runnable, non-authoritative layers, not a silent change to
what the canonical dataset claims to know.

## What this doesn't change

Neither layer alters the project's core guarantee. `role_level`,
`workplace_type`, `city`, `is_south_africa`, and every other canonical
field remain exactly as conservative and rule-derived as before — still
built on "unknown is better than guessing." Both layers are additive
opinions, clearly namespaced (`ml_*` / `llm_*`), gitignored as derived
artifacts, and visible in the dashboard specifically so a reviewer can
compare them against the canonical label rather than mistake one for the
other.
