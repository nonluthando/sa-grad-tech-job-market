# Explainable role-classification engine

The canonical `role_level` remains the conservative production label. The new
scored inference is stored alongside it for evaluation:

- `inferred_role_level`
- `role_level_score`
- `role_level_confidence`
- `role_level_score_evidence`
- `is_talent_pool`

This avoids silently replacing stable rules before the scored model has been
reviewed against real postings.

## Inferred levels

- internship
- graduate
- junior
- mid_level
- senior
- ambiguous

Two years of experience alone remains ambiguous because employers use it for
both junior and intermediate roles. Three to four years is treated as likely
mid-level, while five or more years is treated as likely senior.

Explicit title evidence remains authoritative. A title containing `Senior`,
`Lead`, `Principal`, `Manager`, or equivalent cannot be downgraded by weaker
description evidence.

Talent-pool detection is independent of seniority and should be excluded or
shown separately in vacancy-volume analysis.
