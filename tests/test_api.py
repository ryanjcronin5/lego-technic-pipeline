import pytest
from fastapi.testclient import TestClient

from technic.api import create_app


@pytest.fixture
def client(loaded):
    return TestClient(create_app(loaded))


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_dashboard_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Technic Insights" in res.text
    assert client.get("/static/app.js").status_code == 200


def test_summary_endpoint(client):
    body = client.get("/api/summary").json()
    assert body["technic_sets"] == 5
    assert body["source"] == "fixtures"
    assert body["last_refreshed"] is not None


def test_biggest(client):
    rows = client.get("/api/sets/biggest?limit=2").json()
    assert [r["set_num"] for r in rows] == ["42115-1", "42083-1"]
    assert rows[0]["theme"] == "Supercar Special"


def test_search_is_case_insensitive_and_technic_only(client):
    assert [r["set_num"] for r in client.get("/api/sets/search?q=bugatti").json()] == ["42083-1"]
    assert client.get("/api/sets/search?q=falcon").json() == []


def test_set_detail_and_404(client):
    body = client.get("/api/sets/42083-1").json()
    assert body["distinct_parts"] == 3 and body["is_technic"] is True
    assert client.get("/api/sets/nope-1").status_code == 404
    assert client.get("/api/sets/nope-1/similar").status_code == 404


def test_similar_and_compare(client):
    similar = client.get("/api/sets/42083-1/similar").json()
    assert similar[0]["set_num"] == "8880-1"
    comp = client.get("/api/compare", params={"a": "42083-1", "b": "8880-1"}).json()
    assert comp["shared_parts"] == 2


def test_parts_top(client):
    assert client.get("/api/parts/top?limit=1").json()[0]["part_num"] == "2780"


def test_validation_errors(client):
    assert client.get("/api/sets/search?q=a").status_code == 422
    assert client.get("/api/sets/biggest?limit=0").status_code == 422


def test_empty_database_returns_503(engine):
    client = TestClient(create_app(engine))
    res = client.get("/api/summary")
    assert res.status_code == 503
    assert "technic-etl" in res.json()["detail"]
