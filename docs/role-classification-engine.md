# Explainable role-classification engine

The canonical `role_level` remains the conservative production label. A
scored inference is stored alongside it for evaluation, and two further
optional, non-canonical suggestion layers are available on top of both:

- `inferred_role_level`
- `role_level_score`
- `role_level_confidence`
- `role_level_score_evidence`
- `is_talent_pool`

This avoids silently replacing stable rules before the scored model has been
reviewed against real postings. Neither optional layer below ever overwrites
`role_level` or `inferred_role_level`.

## Inferred levels

- internship
- graduate
- junior
- mid_level
- senior
- ambiguous (scored system only; the canonical system reports `unspecified`)

Two years of experience alone remains ambiguous because employers use it for
both junior and intermediate roles. Three to four years is treated as likely
mid-level, while five or more years is treated as likely senior.

## Title-word authority (revised)

Explicit title evidence remains authoritative, but not all senior-sounding
words are equally trustworthy, and an explicit early-career word in the
*same* title can still win. Title words are split into two tiers:

- **Unambiguous** (`Senior`, `Staff`, `Principal`, `Director`, `VP`, `Chief`)
  always wins, even over an explicit early-career word in the same title.
- **Overloaded** (`Manager`, `Lead`, `Architect`, `Head of`) is a real senior
  signal on its own, but it also appears in genuinely early-career titles
  ("Junior Product Manager", "Project Manager (Junior)"). An explicit
  early-career word in the same title beats these specifically.

One shape needs a guard rather than a flat precedence flip: "Graduate
Programme Manager" is a senior role managing an early-career programme, not
a junior one — the early-career word describes the programme, not this
role's own seniority. A dedicated pattern detects "graduate/internship/
trainee + programme/program" and lets the overloaded senior word win only
then.

`Associate` is weaker still than `Junior`/`Graduate`/`Intern` — some
industries use it for a senior grade (e.g. "Associate Data Architect"). It
only resolves to `junior` when paired with a specific domain word
(`Associate Software Engineer`, `Associate Platform Infrastructure
Engineer`, ...), and it loses outright to an overloaded senior word
elsewhere in the same title.

A vague description phrase ("no experience required") is weaker evidence
than an explicit numeric experience range, and can be badly
decontextualized (e.g. "Management experience: no experience required"
alongside "7-10 years" overall experience stated elsewhere in the same
description). When an explicit 5+ year requirement is also present, the
weak phrase no longer decides the label on its own — the canonical system
falls back to `unspecified` rather than guess, and the scored system falls
through to its numeric-years branch instead.

See [`docs/regex-classification-audit.md`](regex-classification-audit.md)
for the full investigation (real postings, before/after evidence) behind
each of the rules above, plus one known residual edge case left
intentionally unfixed.

Talent-pool detection is independent of seniority and should be excluded or
shown separately in vacancy-volume analysis.

## Optional suggestion layers

Two further layers exist purely to cover what the deterministic rules
leave `unspecified` (or, for workplace/location, what they never attempt at
all). Both are manually-run, both are gitignored derived artifacts, and
neither is ever merged into the canonical fields.

### Scikit-learn second-stage classifier

`scripts/train_role_classifier.py` trains a TF-IDF + logistic regression
model on jobs the deterministic rules already labelled with high
confidence, then suggests a level for jobs still `unspecified`. Output
fields: `ml_suggested_role_level`, `ml_role_level_confidence`. Evaluated
with macro-F1 (not accuracy) because the training labels are heavily
imbalanced.

### Gemini-assisted classifier

`scripts/classify_with_gemini.py` asks Gemini to suggest `role_level`,
`workplace_type`, and `city` for target-market jobs still missing one or
more of them — the only one of the three layers that also covers workplace
type and location, since the rule-based and scikit-learn layers only ever
address role level. A job's suggestion keeps only the fields that were
actually unresolved for it, even though every request asks about all
three for one consistent schema. Output fields: `llm_suggested_role_level`,
`llm_suggested_workplace_type`, `llm_suggested_city`, plus a confidence and
rationale per field.

### Keeping the layers consistent

`tests/test_role_level_consistency.py` checks the deterministic and scored
role-level classifiers agree on a shared fixture set, so a future fix to
one can't silently drift from the other the way the "Associate" handling
once did.
