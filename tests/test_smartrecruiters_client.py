import json

from src.ingestion.config import SmartRecruitersSource
from src.ingestion.smartrecruiters import SmartRecruitersClient


class FakeResponse:
    def __init__(self, url, payload, content_type="application/json"):
        self.url = url
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status_code = 200
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        pass


class QueueSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


def _source(**overrides):
    defaults = dict(
        name="Standard Bank",
        token="standardbankgroup",
        host="https://api.smartrecruiters.test",
        site="StandardBankGroup",
        request_delay_seconds=0,
    )
    defaults.update(overrides)
    return SmartRecruitersSource(**defaults)


def test_smartrecruiters_client_collects_listing_and_details():
    session = QueueSession(
        [
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {
                    "totalFound": 2,
                    "content": [
                        {"id": "1", "name": "Junior Developer"},
                        {"id": "2", "name": "Data Engineer"},
                    ],
                },
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/1",
                {"id": "1", "name": "Junior Developer"},
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/2",
                {"id": "2", "name": "Data Engineer"},
            ),
        ]
    )
    result = SmartRecruitersClient(session=session, sleep=lambda _: None).fetch_source(
        _source()
    )
    payload = json.loads(result.raw_bytes)
    assert result.job_count == 2
    assert result.listing_page_count == 1
    assert len(payload["job_pages"]) == 2
    assert payload["job_index"][0]["id"] == "1"
    assert session.calls[0][0] == "GET"


def test_smartrecruiters_client_paginates_across_pages():
    session = QueueSession(
        [
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {"totalFound": 3, "content": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]},
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {"totalFound": 3, "content": [{"id": "3", "name": "C"}]},
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/1",
                {"id": "1", "name": "A"},
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/2",
                {"id": "2", "name": "B"},
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/3",
                {"id": "3", "name": "C"},
            ),
        ]
    )
    result = SmartRecruitersClient(session=session, sleep=lambda _: None).fetch_source(
        _source(page_size=2)
    )
    assert result.job_count == 3
    assert result.listing_page_count == 2
    assert result.detail_page_count == 3


def test_smartrecruiters_client_rejects_posting_missing_id():
    session = QueueSession(
        [
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {"totalFound": 1, "content": [{"name": "No id"}]},
            ),
        ]
    )
    import pytest

    with pytest.raises(ValueError, match="missing an id"):
        SmartRecruitersClient(session=session, sleep=lambda _: None).fetch_source(_source())


def test_smartrecruiters_client_rejects_changing_total():
    session = QueueSession(
        [
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {"totalFound": 3, "content": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]},
            ),
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {"totalFound": 4, "content": [{"id": "3", "name": "C"}]},
            ),
        ]
    )
    import pytest

    with pytest.raises(ValueError, match="reported job count changed"):
        SmartRecruitersClient(session=session, sleep=lambda _: None).fetch_source(
            _source(page_size=2)
        )


def test_smartrecruiters_client_rejects_incomplete_pagination():
    session = QueueSession(
        [
            FakeResponse(
                "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
                {"totalFound": 5, "content": [{"id": "1", "name": "A"}]},
            ),
        ]
    )
    import pytest

    with pytest.raises(ValueError, match="exceeded max_pages"):
        SmartRecruitersClient(session=session, sleep=lambda _: None).fetch_source(
            _source(page_size=1, max_pages=1)
        )
