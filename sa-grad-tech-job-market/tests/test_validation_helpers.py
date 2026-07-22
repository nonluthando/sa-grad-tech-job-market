from scripts.validate_sources import (
    NormalizedJob,
    contains_any,
    normalize_greenhouse,
    normalize_lever,
    required_fields_complete,
)


def test_contains_any_is_case_insensitive():
    assert contains_any("Cape Town, South Africa", ["south africa"])
    assert contains_any("Senior DATA Analyst", ["data"])


def test_required_fields_complete():
    complete_job = NormalizedJob(
        source_job_id="123",
        title="Data Analyst",
        location="Cape Town",
        description="Analyse data.",
        application_url="https://example.com/jobs/123",
    )
    assert required_fields_complete(complete_job)


def test_normalize_greenhouse():
    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Software Engineer",
                "location": {"name": "Cape Town"},
                "content": "<p>Build software.</p>",
                "absolute_url": "https://example.com/jobs/123",
            }
        ]
    }
    jobs = normalize_greenhouse(payload)
    assert jobs[0].source_job_id == "123"
    assert jobs[0].location == "Cape Town"


def test_normalize_lever_prefers_all_locations():
    payload = [
        {
            "id": "abc",
            "text": "Data Analyst",
            "categories": {
                "location": "Cape Town, ZA",
                "allLocations": ["Cape Town, ZA", "Johannesburg, ZA"],
            },
            "descriptionPlain": "Analyse data.",
            "applyUrl": "https://example.com/apply/abc",
        }
    ]
    jobs = normalize_lever(payload)
    assert "Cape Town, ZA" in jobs[0].location
    assert "Johannesburg, ZA" in jobs[0].location
