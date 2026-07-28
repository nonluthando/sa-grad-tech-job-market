# Employer Registry

`config/employers.json` stores employer-level metadata separately from
provider-specific collection settings in `config/sources.json`.

## Status meanings

- `active`: a collector is configured and enabled or available for the employer.
- `candidate`: the employer is approved for research, but no collector is enabled.
- `paused`: a previously configured source is intentionally disabled.
- `retired`: the employer is no longer part of the intended coverage.

Candidate entries do not trigger collection. Before promoting one to `active`:

1. Verify the official careers URL.
2. Identify the recruitment platform and public endpoint.
3. Confirm that vacancy terms allow public collection.
4. Add a source entry containing the registry `employer_id`.
5. Run source validation and the full test suite.

Parent companies and brands are metadata for analysis. They do not merge vacancy
records during ingestion or deduplication.
