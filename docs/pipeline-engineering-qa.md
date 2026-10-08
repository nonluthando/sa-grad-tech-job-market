# Pipeline Engineering Q&A

A reference answer set for interview/CV questions about this project's engineering
depth, written from verified evidence (file:line citations, real commit hashes, real
test names, exact git-authorship counts) rather than from memory or narrative framing.
Where the evidence has a gap or a caveat, it's stated as one — this doc is meant to
survive a skeptical follow-up question, not just read well.

## 1. Hardest / most interesting failure

**SAP SuccessFactors's pagination** is the most technically interesting problem in
the ingestion layer. Every other paginated provider (Workday, Oracle HCM,
SmartRecruiters) takes `offset`/`limit` as a normal JSON POST field or query
parameter. SuccessFactors's public career-site pagination instead encodes the offset
**as a literal path segment appended to the URL** (`src/ingestion/successfactors.py:66-72`):

```python
def _listing_page_url(base_url: str, offset: int) -> str:
    if offset == 0:
        return base_url
    parsed = urlparse(base_url)
    path = f"{parsed.path.rstrip('/')}/{offset}/"
    return parsed._replace(path=path).geturl()
```

There is no JSON API at all — it's server-rendered HTML scraped with BeautifulSoup.
The total result count is regex-parsed out of free-text English copy:

```python
_RESULTS_PATTERN = re.compile(r"Results\s+\d+\s*[–—-]\s*\d+\s+of\s+(\d+)", re.IGNORECASE)
```

and each job's location/date comes from walking to the parent `<tr>` and reading
trailing table cells after the title cell — one SAP template customization away from
silently breaking. The fix wasn't to make this robust to arbitrary HTML drift; it was
to make it **fail loudly instead of guessing**. `fetch_source`'s own docstring states
the intent directly: *"fail rather than silently keep partial pages."* If the scraped
total changes mid-pagination, or a page adds zero new jobs before the total is
reached, or the final count doesn't match the reported total, it raises `ValueError`
rather than emitting a partial snapshot.

**The more instructive failure**, worth leading with if pressed on "found a real bug":
commit `15d633b`. `src/transformation/workable.py` and `breezy_hr.py` existed as stub
transformers that parsed fields but never produced a real canonical job, were never
wired into `SUPPORTED_SNAPSHOT_PROVIDERS` or `dataset.py`'s provider dispatch, and
nothing referenced them. **Collection succeeded. Snapshots were written to disk
correctly. The pipeline reported success. But four real employers' jobs (Stitch,
Clickatell, Shoprite/ShopriteX, Mukuru) could never reach `jobs.parquet` — silently,
with no error or warning anywhere.** A crash is loud; a silently-empty code path
isn't, which makes it the more dangerous class of bug. It was caught by auditing the
pipeline's actual data flow (checking what code reads each snapshot directory), not
by a test failing — no test was protecting against it.

## 2. Provider failure / unexpected-data handling

Confirmed directly in `src/ingestion/collect.py`: every one of the ten
`collect_<provider>_source` functions wraps its client call in its own
`try/except (requests.RequestException, ValueError, OSError)` and converts a failure
to `CollectionResult(status="failed", ...)` — it never propagates. `main()` runs every
configured source as a plain list comprehension with no surrounding try/except needed,
because each element independently produces a result. This is proven by real tests,
not just inferred: `tests/test_ashby_collection.py::test_collect_ashby_source_reports_failure`
injects a client that raises and asserts the result comes back `status == "failed"`,
not an escaped exception; `tests/test_smartrecruiters_collection.py` has the equivalent.

**The honest caveat**: `collect_configured_source` validates each source's *config*
(e.g. does a Workday source have `host`/`tenant`/`site`?) before delegating to the
provider function, and that validation is a bare `raise ValueError(...)` **outside any
try/except**. This happened for real — commit `9eb5938`'s message states that 9
misconfigured sources *"made `src.ingestion.collect` fail immediately for the entire
pipeline, not just these sources."* The fix was pragmatic (disable the broken sources
in config), not structural (the gap in `collect.py` itself is still there). The
accurate claim: a well-configured source that fails at runtime is fully isolated and
tested; a source missing required config is still a single point of failure for the
whole run.

## 3. Partial failure at the CI/scheduling level — it runs, and it flags

`.github/workflows/refresh-dashboard.yml`'s collect step is:

```yaml
- name: Collect public vacancy snapshots
  id: collect
  continue-on-error: true
  run: python -m src.ingestion.collect
```

Because `main()`'s own per-source isolation (above) means collection never crashes
mid-run even when some sources fail, `continue-on-error: true` means: the workflow
proceeds to **Build canonical jobs → Audit unspecified → Extract skills → Build
dashboard marts → Run tests**, all running unconditionally against whatever snapshots
*did* get written that run. The last step is gated specifically on the collect
outcome:

```yaml
- name: Report partial collection failures
  if: steps.collect.outcome == 'failure'
  run: echo "::warning::One or more providers failed. The dashboard was rebuilt from the successful snapshots."
```

So the system is explicitly designed to **ship what succeeded and flag the gap**,
rather than block the whole scheduled refresh on one flaky employer career site. The
commit-and-push step still runs and publishes the (partial) dashboard data; the
warning is a visible annotation on the run, not a failed build.

## 4. Why immutable SHA-256 snapshots

Three distinct problems, confirmed in `src/ingestion/snapshot.py`, not one:

1. **Idempotency** — re-running collection at the same timestamp with the same
   content is a no-op; a *conflicting* payload at the same timestamp raises
   `FileExistsError` rather than silently overwriting history.
2. **Storage dedup across runs** — if a new run's response is byte-identical to a
   prior snapshot, the raw file isn't duplicated, only a fresh metadata sidecar is
   written (so observation history still advances). Visible on disk right now:
   `data/raw/greenhouse/ozow/...metadata.json`'s `raw_file` field points to an
   *earlier* timestamp than the metadata file itself — a run that reused prior bytes.
3. **Tamper/corruption detection on read** — `src/transformation/snapshots.py`
   recomputes the hash of the raw file before trusting it and raises
   `SnapshotReadError("SHA-256 mismatch...")` if it doesn't match, tested directly
   (`test_read_greenhouse_snapshot_rejects_modified_raw_file`), including for each
   base64-embedded page inside multi-page provider bundles independently.

`docs/milestone-2-cleaning.md` states the build fails rather than silently trusting a
snapshot when the hash doesn't match — same "fail loud, not quiet" philosophy as the
SuccessFactors completeness checks. There's no recorded incident of this catching real
corruption in production in the visible history; the mechanism is proven by tests, not
by a war story.

## 5. What the 256 tests cover

Exact count, re-run directly: **256 passed, 0 failed, 45 files.**

- **Provider client failure modes** (malformed JSON, HTTP errors, hidden pagination
  caps, changing totals, exhausted `max_pages`): strong for SmartRecruiters (5 tests)
  and Ashby (4), thinner for SuccessFactors (1), and absent at the client level for
  Workday/Oracle HCM/WP Job Manager. This tracks build order exactly — providers added
  later (Phase 2b) shipped with systematic failure tests from day one; the three the
  README singles out for reliability work are the *least* tested against failure,
  despite having the most complex client code. Worth saying plainly if asked.
- **Snapshot integrity**: 8 tests in `test_transformation_snapshots.py`, 2 more for
  embedded-page tampering specifically in `test_successfactors_snapshots.py`.
- **Dedup**: `test_deduplicate_jobs_keeps_latest_record_and_observation_window` — same
  job ID observed twice with a changed title merges into one record with
  `observation_count == 2`, proving identity is the provider ID, not the title text.
- **Classification**: 31 tests for the rule-based classifier, 18 for the scored
  engine, 12 for cross-system consistency between the two role-level classifiers
  (added specifically to stop the two systems silently disagreeing — see §7/§8).
- **Two end-to-end-*style* tests**, not a true CLI run:
  `test_build_dataset_combines_greenhouse_and_lever_snapshots` writes real multi-provider
  raw fixtures to a temp dir, calls the actual `build_dataset()` entry point, and
  asserts on the final counts (`report["target_market_job_count"] == 4`, etc.) — raw
  snapshot → integrity check → transform → classify → dedup → quality report, in one
  call. A second covers canonical → analytics marts.
  **No test runs the actual CLI commands end-to-end via subprocess.**
  `test_dashboard_workflow.py` only asserts the right command strings appear as
  literal text in the GitHub Actions YAML — it verifies wiring, not behavior.

## 6. What validation caught before it reached the data

- **`15d633b`** (§1) — four employers silently absent from the entire dataset, zero
  errors anywhere.
- **The regex-classification audit** (`docs/regex-classification-audit.md`) — six
  confirmed bugs, each verified against real postings, not synthetic fixtures:
  "Junior Product Manager (Marketplace)" and "Project Manager (Junior)" were labeled
  `senior` because a generic word like "Manager" outranked the explicit "Junior" in
  the same title; a bare single-letter "C" skill pattern false-tagged 167 of 1,661
  jobs (10%); a Nedbank posting requiring 7–10 years' experience was labeled `junior`
  with *high confidence* because "No experience required" — actually answering a
  sub-question about *management* experience specifically — outranked the explicit
  range stated one sentence earlier. All found by checking the classifiers against
  the live dataset rather than trusting the code.

## 7. What triggered the scikit-learn addition — a real, specific gap, not a generic "add ML"

`scripts/audit_unspecified.py` is not something built this session — it traces back
to the first commit in this repo's visible history. Running it (or just querying the
live dataset) shows: **of 196 target-market jobs, 89 (45%) have `role_level ==
unspecified`.** That's the deterministic rules declining to call it on nearly half
the market the project exists to describe — a large, real, pre-existing gap, visible
through the project's own tooling, not a hypothesis.

The scikit-learn second-stage classifier (`scripts/train_role_classifier.py`) was
scoped specifically to address that population: it trains only on jobs the
deterministic rules already labelled with high confidence, then predicts a level for
exactly the set `audit_unspecified.py` flags — the same population, the same filter
(`is_target_market is True and role_level == "unspecified"`), deliberately kept
consistent with the existing audit tool rather than invented separately. Evaluated
with macro-F1 (91.0%) rather than accuracy, because the training labels are
imbalanced (650 `senior` vs. 4 `mid_level` examples) and accuracy alone would have
hidden the model's real weak point — 61.3% recall on `junior`, meaning it misses
roughly 2 in 5 genuine junior postings. That weakness is reported, not buried under a
reassuring headline number.

The later Gemini-assisted layer followed the same discipline: `workplace_type` was
unresolved for 116 of 196 target-market jobs (59% — a bigger gap than role level) and
`city` for 13, and scikit-learn only ever addresses role level, so Gemini was scoped
to the two fields nothing else was covering, not role level again.

## 8. Most defensible architectural decision: stable-ID deduplication + no job aggregators

This is the strongest, most consistently-enforced design decision in the codebase,
and it holds together as one coherent policy:

- **Job identity** is `{provider}:{source_token}:{provider's own job ID, or a hash of
  the application URL, or a hash of the content as a last resort}` — title is never
  part of the key (`src/transformation/greenhouse.py:46-58`, identical pattern across
  all 10 providers).
- **Dedup** (`dataset.py::deduplicate_jobs`) groups strictly by that exact key,
  proven by a test where the *same* job ID gets a *changed* title across two
  observations and correctly merges into one record, keeping the latest title. Two
  different postings with similar titles structurally cannot collide, because they
  have different provider IDs — no fuzzy/title matching exists anywhere in `src/`
  (confirmed by grep).
- **The no-aggregator rule is enforced with real judgment, not just pattern-matched**:
  `docs/source-and-role-expansion-research.md` catches Woolworths' careers portal as a
  **PNet white-label instance disguised behind Woolworths' own domain** and excludes
  it anyway: *"this is a PNet-branded backend; scraping it would violate the
  project's explicit 'do not scrape PNet' rule even though the front door is
  Woolworths' own domain."*
- **The stated rationale** (`docs/data-source-assessment.md`) is specific: *"preferred
  over a paid aggregator because the original employer, posting identifier, public
  URL and exact source response remain auditable. The trade-off is maintaining
  several small provider adapters instead of one external API dependency."* A real,
  defensible trade-off — provenance and auditability per record, at the cost of
  maintaining 10 adapters instead of 1.

## 9. AI vs. personal authorship — the honest accounting

Pulled directly from git history, not estimated: **135 commits total, 96 automated
bot commits (scheduled data refreshes, not code), 31 commits authored by `Claude
<noreply@anthropic.com>`, and 8 commits authored by the project owner — every one of
which is a "Merge pull request #N" click, not an authored code change** (confirmed:
`git log --author="Luthando Mbuyane"` returns exactly those 8 merge commits and
nothing else). The repo is a shallow clone, so history before 2026-09-04 isn't
visible from here — if earlier work predates what's checked in, it can't be confirmed
or ruled out from this evidence alone.

What this means for a CV, stated plainly: **the visible authorship record does not
support claiming personal authorship of the adapter code, the classification engine,
or the test suite.** What it does support, concretely: setting the scope and
non-negotiables (no aggregators, no fuzzy matching, conservative/explainable-over-convenient
classification — all stated as deliberate trade-offs in the project's own docs);
noticing real gaps through the project's own tooling and directing the fix (§7's
scikit-learn trigger is a clean example — a specific number from a specific audit
tool, not a vague "let's try ML"); and reviewing AI-generated output rather than
accepting it — including, in this exact project, catching stale cached dashboard data,
insisting on re-verification against the live dataset instead of a stale report, and
making every merge decision. That's a real, describable skill — directing and
validating an AI-assisted engineering pipeline — and it's honest in a way that "I
built this" would not be.
