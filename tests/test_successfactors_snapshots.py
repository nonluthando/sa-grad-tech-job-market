import base64
import hashlib
import json
from pathlib import Path

import pytest

from src.transformation.snapshots import (
    SnapshotReadError,
    read_successfactors_snapshot,
)


DETAIL = b"""
<html><body><div class="job">
<h1>Software Developer</h1>
<div class="jobGeoLocation">Location: Johannesburg, ZA</div>
<div>Date: 20 Jul 2026</div>
<div class="jobdescription"><p>Build software using Java.</p></div>
</div></body></html>
"""
LISTING = b"<html><body>Results 1 - 1 of 1</body></html>"


def page(url: str, body: bytes, **extra):
    return {
        "requested_url": url,
        "final_url": url,
        "status_code": 200,
        "content_type": "text/html",
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "body_base64": base64.b64encode(body).decode("ascii"),
        **extra,
    }


def write_bundle(tmp_path: Path, tamper_embedded_hash: bool = False) -> Path:
    source_directory = tmp_path / "successfactors" / "example"
    source_directory.mkdir(parents=True)
    detail_page = page(
        "https://example.test/job/Johannesburg-Software-Developer/1001/",
        DETAIL,
        source_job_id="1001",
    )
    if tamper_embedded_hash:
        detail_page["content_sha256"] = "0" * 64
    payload = {
        "provider": "successfactors",
        "source_token": "example",
        "listing_url": "https://example.test/go/All/123/",
        "reported_job_count": 1,
        "listing_pages": [page("https://example.test/go/All/123/", LISTING)],
        "job_index": [
            {
                "source_job_id": "1001",
                "title": "Software Developer",
                "location_raw": "Johannesburg, ZA",
                "published_text": "20 Jul 2026",
                "application_url": "https://example.test/job/Johannesburg-Software-Developer/1001/",
            }
        ],
        "job_pages": [detail_page],
    }
    raw_bytes = (json.dumps(payload) + "\n").encode()
    raw_path = source_directory / "snapshot.json"
    raw_path.write_bytes(raw_bytes)
    metadata_path = source_directory / "snapshot.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source": "successfactors",
                "source_name": "Example Bank",
                "source_token": "example",
                "collected_at": "2026-07-23T12:00:00Z",
                "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "source_job_count": 1,
                "raw_file": raw_path.name,
            }
        )
    )
    return metadata_path


def test_read_successfactors_snapshot_verifies_and_parses_bundle(tmp_path):
    snapshot = read_successfactors_snapshot(write_bundle(tmp_path))

    assert snapshot.provider == "successfactors"
    assert len(snapshot.jobs) == 1
    assert snapshot.jobs[0]["source_job_id"] == "1001"
    assert snapshot.jobs[0]["title"] == "Software Developer"


def test_read_successfactors_snapshot_rejects_modified_embedded_page(tmp_path):
    metadata_path = write_bundle(tmp_path, tamper_embedded_hash=True)

    with pytest.raises(SnapshotReadError, match="embedded page SHA-256 mismatch"):
        read_successfactors_snapshot(metadata_path)
