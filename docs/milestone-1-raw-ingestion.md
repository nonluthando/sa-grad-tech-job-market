# Milestone 1 — Greenhouse Raw Ingestion

## Goal

Collect current public Greenhouse job-board responses and preserve the original
response bytes before cleaning, filtering or modelling them.

## Scope

The first adapter collects all enabled `greenhouse` entries in
`config/sources.json`:

- Takealot Group
- Luno
- Impact.com

Lever and HTML sources remain validation-only until their own ingestion adapters
are implemented.

## Raw-data contract

Each successful source request produces:

```text
data/raw/greenhouse/{board_token}/{timestamp}.json
data/raw/greenhouse/{board_token}/{timestamp}.metadata.json
```

The JSON snapshot contains the exact HTTP response bytes. The metadata sidecar
contains:

- provider and source name;
- board token and endpoint;
- UTC collection timestamp;
- HTTP status and content type;
- SHA-256 content hash;
- byte count;
- source-reported job count; and
- raw snapshot filename.

Each command run also writes a summary under `data/raw/_runs/`.

## Duplicate policy

Before writing, the snapshot store compares the response SHA-256 hash with prior
metadata for that board. Identical content is reported as `duplicate` and is not
written again.

This prevents repeated local runs from creating fake historical observations.

## Failure policy

Sources are attempted independently. Successful raw responses are preserved even
when another source fails, but the command exits with status `1` when any source
fails. This makes failures visible to later automation instead of silently
publishing incomplete data.

Configuration errors exit with status `2`.

## Commands

Collect all enabled Greenhouse sources:

```bash
python -m src.ingestion.collect
```

Collect one board:

```bash
python -m src.ingestion.collect --source-token takealotgroup
```

Use a temporary output directory while testing manually:

```bash
python -m src.ingestion.collect --raw-root /tmp/job-market-raw
```

Run automated tests:

```bash
pytest
```

## Exit condition

Milestone 1 passes when one command retrieves all configured Greenhouse boards,
preserves exact raw payloads and metadata, skips duplicate content, and returns a
non-zero status for failed requests.
