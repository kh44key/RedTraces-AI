"""Local forum findings API matching the dashboard's filter contract."""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from unified_cti_api import require_api_key

DB = Path(os.getenv("FORUM_DATABASE", "/data/forums.db"))
DB.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(DB) as conn:
    conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, first_seen_utc TEXT NOT NULL,
        page_title TEXT, content_snippet TEXT, matched_keywords TEXT,
        severity TEXT, score REAL, source TEXT DEFAULT 'manual')""")

app = FastAPI(title="RedTraces AI Forum API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"])

class AlertIn(BaseModel):
    url: str = Field(min_length=1)
    page_title: str
    content_snippet: str
    matched_keywords: list[str] = Field(default_factory=list)
    severity: str = "MEDIUM"
    score: float = Field(default=50, ge=0, le=100)

@app.get("/api/health")
def health():
    return {"status": "ok", "collection_enabled": False, "mode": "local ingestion"}

@app.post("/api/alerts", dependencies=[Depends(require_api_key)])
def ingest(item: AlertIn):
    with sqlite3.connect(DB) as conn:
        conn.execute("""INSERT INTO alerts
          (url,first_seen_utc,page_title,content_snippet,matched_keywords,severity,score)
          VALUES (?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
          page_title=excluded.page_title,content_snippet=excluded.content_snippet,
          matched_keywords=excluded.matched_keywords,severity=excluded.severity,score=excluded.score""",
          (item.url, datetime.now(timezone.utc).isoformat(), item.page_title,
           item.content_snippet, json.dumps(item.matched_keywords), item.severity.upper(), item.score))
    return {"status": "saved"}

@app.get("/api/data")
def data(period: str = "all", search: str = "", keyword: str = "",
         date_from: str = "", date_to: str = "", min_score: float = 0,
         limit: int = Query(150, ge=1, le=5000)):
    now = datetime.now(timezone.utc)
    days = {"24h": 1, "7d": 7, "30d": 30, "365d": 365}
    if period not in {*days, "all"}:
        raise HTTPException(422, "Invalid period")
    try:
        start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc) if date_from else None
        end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1) if date_to else now
    except ValueError:
        raise HTTPException(422, "Dates must use YYYY-MM-DD")
    selected = "custom" if date_from or date_to else period
    if selected != "custom" and period in days:
        start = now - timedelta(days=days[period])
    if start and start > end:
        raise HTTPException(422, "Start date must precede end date")
    conditions, params = ["score >= ?", "julianday(first_seen_utc) <= julianday(?)"], [min_score, end.isoformat()]
    if start:
        conditions.append("julianday(first_seen_utc) >= julianday(?)")
        params.append(start.isoformat())
    if search or keyword:
        conditions.append("(page_title LIKE ? OR content_snippet LIKE ? OR matched_keywords LIKE ?)")
        params.extend([f"%{search or keyword}%"] * 3)
    where = " AND ".join(conditions)
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM alerts WHERE {where} ORDER BY first_seen_utc DESC LIMIT ?", [*params, limit])]
        severity = {r[0]: r[1] for r in conn.execute(f"SELECT severity, COUNT(*) FROM alerts WHERE {where} GROUP BY severity", params)}
    for row in rows:
        row["matched_keywords"] = json.loads(row["matched_keywords"])
    return {"alerts": rows, "total": sum(severity.values()), "severity": severity,
            "period": selected, "range_start_utc": start.isoformat() if start else None,
            "range_end_utc": end.isoformat(), "monitored_sources": 0}
