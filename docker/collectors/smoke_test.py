"""Isolated functional checks; run inside the unified-api container."""
import os
import tempfile
from datetime import datetime, timezone

with tempfile.TemporaryDirectory() as temp:
    os.environ["UNIFIED_CTI_DATABASE_URL"] = f"sqlite:///{temp}/test.db"
    os.environ["FORUM_DATABASE"] = f"{temp}/forums.db"
    os.environ["UNIFIED_CTI_API_KEY"] = "test-only-key"
    from fastapi.testclient import TestClient
    from unified_cti_api import app
    from forums_api import app as forums
    headers = {"X-API-Key": "test-only-key"}
    with TestClient(app) as client:
        item = dict(source_type="manual", source_name="test", content="test observation",
                    external_id="unique", occurred_at=datetime.now(timezone.utc).isoformat())
        assert client.post("/api/v1/findings", json=item).status_code == 401
        first = client.post("/api/v1/findings", json=item, headers=headers)
        assert first.status_code == 201, first.text
        second = client.post("/api/v1/findings", json=item, headers=headers)
        assert second.json()["id"] == first.json()["id"]
        assert len(client.get("/api/v1/findings").json()) == 1
        assert client.get("/api/v1/findings?severity=critical").json() == []
        assert client.post("/api/v1/findings", json={**item, "confidence": 101}, headers=headers).status_code == 422
    with TestClient(forums) as client:
        alert = dict(url="https://example.invalid/test", page_title="test signal",
                     content_snippet="synthetic check", severity="high", score=70)
        assert client.post("/api/alerts", json=alert).status_code == 401
        assert client.post("/api/alerts", json=alert, headers=headers).status_code == 200
        result = client.get("/api/data?period=24h&search=signal").json()
        assert result["period"] == "24h" and result["total"] == 1
        assert client.get("/api/data?min_score=90").json()["total"] == 0
        assert client.get("/api/data?date_from=invalid").status_code == 422
    print("PASS: authentication, ingestion, timestamps, deduplication, validation and forum filters")
