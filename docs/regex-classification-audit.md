# Regex-Based Classification Audit

> **Status: all three confirmed bugs below are fixed** (commit following this
> audit). Findings are kept as-written for the record; each one now ends with
> a "Fixed" note describing the change and the re-verified numbers.

Every classification in this pipeline is a deterministic regex match, not a model —
that's a deliberate, explainable-by-design choice. This audit inventories every
regex-driven classifier in the codebase, verifies each one against the live
dataset (`data/processed/jobs.parquet`, 1,661 jobs, 196 target-market), and
reports what's working, what's silently wrong, and what's merely risky.

## Inventory

| Module | Classifies | Output fields |
|---|---|---|
| `src/role_classification/patterns.py` + `evidence.py` + `classifier.py` + `scorer.py` | Scored role-level inference | `inferred_role_level`, `role_level_score`, `role_level_confidence`, `role_level_score_evidence` |
| `src/transformation/classification.py` | Canonical (conservative) role level, technology role, location, workplace type | `role_level`, `role_level_evidence`, `is_technology_role`, `technology_evidence`, `city`/`province`/`country`/`is_south_africa`, `workplace_type` |
| `src/skills/taxonomy.py` + `extractor.py` | Skills, soft skills, degree requirements, experience years | `skills`, `soft_skills`, `degree_required`, `degree_fields`, `minimum_experience_years` |

Two **independent, hand-maintained regex systems** classify role level
(`role_classification/` and `transformation/classification.py`). That duplication
is architecturally intentional — one produces a scored inference, the other a
conservative canonical label — but it means the same concept ("what counts as a
senior-level title word?") is encoded twice, by hand, and can silently drift.
It already has.

---

## Confirmed bugs (verified against live data)

### 1. "Senior-word-wins" fires even when the title explicitly says "Junior" — CRITICAL

Both role-level systems check an unordered bag of title words for a senior
trigger (`manager`, `lead`, `director`, `architect`, `head of`, `staff`,
`principal`, `vp`, `chief`) **before** ever looking at explicit early-career
words in the same title. Word order and co-occurrence are ignored.

Verified on the live dataset — titles containing an explicit early-career word
*and* a senior-trigger word:

| Title | `role_level` | `inferred_role_level` | In target market? |
|---|---|---|---|
| **Junior Product Manager (Marketplace)** | `senior` | `senior` | ✅ yes |
| **Project Manager (Junior)** | `senior` | `senior` | ✅ yes |
| Junior Social Media Manager | `senior` | `senior` | no |
| Junior Creator Campaign Manager | `senior` | `senior` | no |
| Junior Publisher Development Manager | `senior` | `senior` | no |
| Junior Marketing Product Manager | `senior` | `senior` | no |

Two of these are in the 196-job target-market set, and **both are mislabeled
senior when the posting's own title says the opposite.** The docstring in
`classify_role_level` ("Senior title terms always win... must not be downgraded
because the title also contains the word 'graduate'") only reasoned about the
*opposite* collision (senior-sounding title incidentally containing "graduate").
It never considered the reverse: an explicitly junior title that also contains
a generic seniority word like "Manager." The `_AUTHORITATIVE_TITLE_LEVELS`
precedence order in `role_classification/classifier.py` has the identical flaw
— it checks `("senior", "internship", "graduate", "junior")` in that fixed
order against all title evidence found, so "senior" category evidence wins
even when "junior" category evidence from the same title is also present and
arguably more specific.

**Why it matters:** this isn't a rare edge case — "Junior Product Manager" is a
completely normal grad-market job title, and it's being filed as `senior` in
the dataset this project is built to produce.

**Root cause:** both systems treat "does any senior word appear in the title"
as sufficient on its own, rather than resolving the conflict when an explicit
early-career word is *also* present. No test exercises this combination —
`test_senior_title_overrides_early_career_description_and_source_level` in
`tests/test_transformation_classification.py` tests senior-vs-description and
senior-vs-source-level, but not senior-word-vs-junior-word-in-the-same-title.

**Fix direction:** when a title matches both an early-career pattern and a
generic senior-trigger word (`manager`, `lead`, `head of`, `architect`), prefer
the early-career label — these are weaker, overloaded signals (any people
manager has "manager" in the title) compared to unambiguous senior markers
(`senior`, `staff`, `principal`, `director`, `vp`, `chief`), which should
legitimately still win even over an explicit junior word (a title is
unlikely to combine those honestly).

**Fixed.** Both systems now split senior title words into an unambiguous set
(always wins) and an overloaded set (`manager`, `lead`, `head of`,
`architect` — loses to an explicit early-career word in the same title). One
case needed a guard rather than a flat precedence flip: "Graduate Programme
Manager" must stay `senior` (the title's own pre-existing docstring called
this out), because "Graduate" there describes the *programme*, not this
role's seniority. A new pattern (`"graduate|internship|trainee" + "programme/
program"`) detects that shape and lets the overloaded senior word win only
then. Re-verified against the live dataset: `"Junior Product Manager
(Marketplace)"` and `"Project Manager (Junior)"` now correctly classify as
`junior` in both systems, while `"Graduate Programme Manager"` and
`"Engineering Manager"` still correctly classify as `senior`. A new
parametrized consistency test (`tests/test_role_level_consistency.py`) checks
both systems agree across these cases so this can't silently regress.

### 2. Bare single-letter "C" skill pattern — HIGH, confirmed false-positive at scale

`src/skills/taxonomy.py`:
```python
("C", "programming_language", (r"(?<![\w+#])c(?![\w+#])",)),
```

This matches a lone "c" anywhere it isn't glued to a word character, `+`, or
`#` — which includes list enumerations, abbreviations, and any stray single
letter "C" preceded by punctuation like a period or comma.

Verified against the live dataset: **167 of 1,661 jobs (10%) are tagged with
the "C" skill.** Spot-checking the hits shows it is essentially pure noise —
none of the sampled matches are software-engineering roles:

```
Enterprise Account Executive         -> matched 'C'
Director of Sales, Greater China     -> matched 'C'
Strategic Programs Manager           -> matched 'C'
Strategic Account Manager            -> matched 'C'
Sales and Account Manager            -> matched 'C'
Local Director / Country Manager     -> matched 'c'
Senior HRBP                          -> matched 'C'
```

Compare this to the **"R" rule in the same table**, which got the contextual
guard right:
```python
("R", "programming_language", (r"\br\s+programming\b", r"\busing\s+r\b")),
```
"R" requires a disambiguating phrase; "C" does not. Same risk, inconsistent
rigor applied within the same rule table.

**Fix direction:** give "C" the same treatment as "R" — require
`\bc\s+programming\b`, `\bc\s+language\b`, or similar — or drop it; "C" alone
(not C++/C#) is rare enough in real SA grad-tech postings that a stricter
pattern won't cost meaningful recall.

**Fixed.** Replaced the bare pattern with `c programming`, `c programming
language`, `using c`, and `c language`, each with a `(?!\+)` guard so "using
C" can't match inside "using C++". Re-verified against the live dataset: the
167 false positives are gone and the match count is now **0/1,661** (the one
residual case — "Android Engineer (C++)" matching via "using C" — was caught
and closed by the `(?!\+)` guard). "C" alone essentially never appears this
way in the current dataset; if a genuine case ever does, the stricter pattern
will still catch `"C programming"`/`"C language"` phrasing.

### 3. "Associate" role-level split between the two systems — MEDIUM, confirmed

Already surfaced in conversation via the real job *"Associate Platform
Infrastructure Engineer"* (Impact.com): `role_classification/patterns.py`
matches bare `\bassociate\b` as junior-level evidence (high confidence), while
`transformation/classification.py`'s canonical classifier only recognizes
`\bassociate\s+(?:software|data|qa|test|cloud|devops|security|business\s+intelligence)\b`
— a much narrower compound pattern that doesn't cover "Associate Platform ..."
or "Associate Infrastructure ...". Result: `role_level="unspecified"` but
`inferred_role_level="junior"` (high confidence) for the same job.

This split is *defensible* as designed (conservative canonical label vs. a
separate scored opinion), but the two patterns weren't deliberately designed
to diverge this way — they drifted, because the same rule is hand-maintained
in two files. It's a real instance of the duplication risk flagged above, not
just a hypothetical one.

**Fixed.** Widened both patterns to the same compound set, adding `platform`
and `infrastructure` so the real Impact.com job is covered, and removed the
bare `\bassociate\b` match from `role_classification/patterns.py` (bare
"Associate" alone is genuinely ambiguous across industries — academic/consulting
seniority vs. tech junior level — so it shouldn't be authoritative, high-confidence
evidence on its own). Re-verified: `"Associate Platform Infrastructure
Engineer"` now gets `role_level=junior` and `inferred_role_level=junior` in
both systems, agreeing for the first time.

---

## Follow-up: mid/senior roles classified as junior

The three fixes above addressed junior-labeled-as-senior. The live dataset
also contains the reverse direction — genuinely mid/senior roles labeled
junior. Two confirmed, fixed; two flagged but left open.

### 4. "Associate X" beats an overloaded senior word the wrong way — CONFIRMED, FIXED

Widening the "Associate" compound pattern (fix #3) introduced a new instance
of the same precedence conflict as fix #1, just inverted: **"Associate Data
Architect"** (Discovery, 8 years' experience required) matched the
associate-junior pattern and was labeled `junior`, even though "Architect" —
an overloaded senior word — was sitting right there in the same title.

**Why this one's different from "Junior Product Manager":** "Junior" is an
explicit, unambiguous seniority word when a company uses it; "Associate" is
not — some industries (and this looks like one of them) use "Associate" as a
senior-track grade. So the fix isn't a flat precedence flip: "Associate"
specifically now loses to an overloaded senior word in the same title, while
"Junior"/"Graduate"/"Intern" still win. Re-verified: `"Associate Data
Architect"` now classifies `senior` in both systems, while `"Associate
Software Engineer"` (no competing senior word) is still correctly `junior`.

### 5. A decontextualized "no experience required" phrase beats an explicit experience range — CONFIRMED, FIXED

A real Nedbank posting, **"Software Quality Engineer II"**, states "Total
number of years of experience: **7 - 10 years**. Management experience as
part of the above years: **No experience required**." The second sentence
answers a specific sub-question ("how much *management* experience"), not
the job's overall requirement — but both systems' generic "no experience
required" pattern matched it anyway and used it to label the whole job
`junior`, ignoring the explicit 7-10 year requirement one sentence earlier.

**Fixed** by adding a numeric-experience sanity check: when an explicit 5+
year requirement is found anywhere in the description, the weak
"no experience required"/"recent graduate"-style phrase patterns are no
longer trusted to decide the label on their own. `role_classification`
(which already extracts experience years) falls through to its existing,
correct numeric-years branch (→ `senior`, medium confidence). The canonical
`transformation.classification` module had no experience-years extraction
of its own in this code path at all — added one (mirroring the same regex
already used in `role_classification/evidence.py` and
`skills/extractor.py`) so it can detect the conflict and fall back to the
conservative `unspecified` rather than guess. Re-verified: this job is now
`senior` (medium confidence) / `unspecified`, not `junior` (high confidence)
in either system.

### Flagged, not fixed — lower confidence or out of scope for now

- **"Associate Engineer I"** (5 years required): `role_classification`
  still returns `junior`, because "Engineer I" is matched as *title*
  evidence (immediately authoritative, before the experience-years sanity
  check ever runs — that check only applies to the weaker *description*-phrase
  fallback). Only one job in the live dataset hits this, and it's genuinely
  ambiguous — "Engineer I" is an authoritative-by-design signal elsewhere
  in the same rule table (deliberately so, same as "Senior" titles beating
  explicit years), so extending the experience-years veto to title-level
  evidence is a bigger, more invasive change than the other fixes here.
  Left as a known residual case rather than patched under time pressure.
- **Age ranges mis-parsed as years of experience.** Several "Learnership"
  postings require applicants to be "between 18 and 25 years old," and the
  experience-years regex (duplicated across `role_classification/evidence.py`,
  `skills/extractor.py`, and now also `transformation/classification.py`)
  has no guard against "years old" phrasing — it reads this as a 25-year
  experience requirement. It caused no wrong label in the current dataset
  only because "Learnership" in the title is unambiguous and authoritative
  on its own, resolving before experience is ever consulted — but the same
  regex, hit on a job with a more neutral title, would produce a badly wrong
  `senior` classification from an age requirement. This is a distinct bug
  in the shared experience-years pattern, not the role-level precedence
  logic, and is out of scope for this pass.

## Design risks (not yet confirmed as causing bad labels, worth tracking)

- **`EXPLICIT_LEVEL_RULES` in `role_classification/patterns.py` is missing
  senior terms that `_SENIOR_TITLE_PATTERNS` in `transformation/classification.py`
  has.** The former's senior list is `(senior, lead, principal, manager)`; the
  latter's is `(senior, staff, principal, lead, manager, director, head of,
  architect, vp, chief)`. A source-provided `explicit_level` field of "Staff"
  or "Director" would not be recognized as senior by the scored system, only
  by the canonical one. Another symptom of hand-duplicated rule tables.
- **No `_TECH_FALSE_POSITIVES`-style guard list exists in `skills/taxonomy.py`.**
  `transformation/classification.py` has a dedicated false-positive guard list
  for technology-role titles (`data capturer`, `software sales`, `technical
  recruiter`, ...). The skills taxonomy has no equivalent for short/ambiguous
  tokens, which is exactly how finding #2 slipped through.
- **Bare `\bmanager\b` as a universal senior signal** is broad by design (any
  "X Manager" title is treated as senior), which is reasonable in isolation,
  but combined with finding #1 it's the specific word responsible for every
  mislabeled "Junior ... Manager" case found above.
- **Single-word technology triggers** (`\bcloud\b`, `\bautomation\b`) are
  broad but, on inspection of the live dataset, didn't produce obviously bad
  matches in the current (small, already-filtered-by-provider) dataset — flagged
  as "watch if source diversity grows" rather than "fix now."

## What's working well (no action needed)

- `_TECH_FALSE_POSITIVES` in `transformation/classification.py` is a good,
  working pattern for guarding against homonym titles ("data capturer" vs.
  "data engineer") — the dataset shows zero false positives from the terms it
  guards against.
- Location/country classification (`_CITY_RULES`, `_COUNTRY_RULES`) is scoped
  to a fixed canonical list and showed no false positives in review.
- Experience-year extraction (`_RANGE_YEARS`/`_SINGLE_YEARS` in both
  `role_classification/evidence.py` and `skills/extractor.py` — itself a third
  instance of near-duplicated regex, worth noting) correctly avoids double-counting
  overlapping spans.
- The "R" programming-language pattern is the right template for how every
  short/ambiguous token should be written.

## Test coverage gaps

- No test exercises a title containing both an explicit early-career word and
  a generic senior-trigger word (the exact shape of bug #1).
- No test exercises the bare "C" skill pattern against a non-technical title
  (the exact shape of bug #2) — existing tests only check Java-vs-JavaScript
  disambiguation, not C-vs-plain-English-letter.
- No test asserts that `role_classification/` and `transformation/classification.py`
  agree on role level for the same input — the kind of cross-system consistency
  check that would have caught the "Associate" drift automatically.

## Recommended fix order

1. **Bug #1** (senior-word-wins over explicit junior title) — highest impact,
   confirmed to mislabel real target-market jobs.
2. **Bug #2** (bare "C") — high false-positive rate, easy fix, no behavior
   trade-off (the stricter pattern loses essentially nothing).
3. **Bug #3** (Associate split) — lower urgency since it only affects the
   `role_level` vs `inferred_role_level` disagreement, not a wrong *dataset*
   label outright (the canonical field just stays conservative/unspecified).
4. Add a cross-system consistency test comparing `classify_role` and
   `classify_role_level` on a shared fixture list, to catch future drift
   between the two hand-maintained rule tables automatically.

All four items are done as of this update: fixes 1–3 above, plus
`tests/test_role_level_consistency.py`. The design risks and "what's working
well" sections below are left as open observations, not yet acted on.
