"""FastAPI application serving collected-message history and live updates."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import redis.asyncio as redis
from sqlalchemy import func, or_, select

from common.db import AsyncSessionFactory, engine, init_db
from common.models import CollectedMessage


OUTPUT_DIRECTORY = Path(os.getenv("OUTPUT_DIRECTORY", "/output"))
STIX_STORE_PATH = Path(
    os.getenv("STIX_STORE_PATH", str(OUTPUT_DIRECTORY / "stix_store.sqlite3"))
)
LEGACY_TELEGRAM_API = os.getenv("TELEGRAM_LEGACY_API_URL", "http://telegram:8000").rstrip("/")
PUBLIC_UPSTREAMS = {
    "twitter": "http://twitter:8000/leaks?limit=200",
    "facebook": "http://facebook:8000/leaks?limit=200",
    "instagram": "http://instagram:8000/leaks?limit=200",
    "forums": "http://forums:8000/api/data?limit=200",
}


def serialize_message(message: CollectedMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "platform": message.platform,
        "source": message.source,
        "raw_text": message.raw_text,
        "author": message.author,
        "url": message.url,
        "collected_at": message.collected_at.isoformat(),
        "posted_at": message.posted_at.isoformat() if message.posted_at else None,
        "metadata": message.metadata_,
        "attachments": message.attachments,
    }


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(title="RedTraces AI", lifespan=lifespan)
frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _request_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = UrlRequest(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urlopen(request, timeout=8) as response:  # nosec B310: fixed Compose URLs
        return json.loads(response.read().decode("utf-8"))


async def _upstream_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    try:
        return await asyncio.to_thread(_request_json, url, payload)
    except (URLError, TimeoutError, ValueError, OSError) as error:
        raise HTTPException(status_code=502, detail="Upstream collector unavailable") from error


def _legacy_row(message: CollectedMessage) -> dict[str, Any]:
    metadata = message.metadata_ or {}
    return {
        "id": f"redtraces-{message.id}",
        "channel": message.source,
        "message_id": metadata.get("message_id"),
        "detected_domains": metadata.get("iocs", {}).get("domains", []),
        "detected_entities": [],
        "text": message.raw_text,
        "message_date": message.posted_at.isoformat() if message.posted_at else message.collected_at.isoformat(),
        "processed_at": message.collected_at.isoformat(),
        "severity": "info",
        "pipeline": "redtraces-core",
        "ioc_count": metadata.get("ioc_count", 0),
    }


async def _core_telegram_rows(keyword: str = "", limit: int = 1000) -> list[dict[str, Any]]:
    clauses = [CollectedMessage.platform == "telegram"]
    if keyword.strip():
        clauses.append(CollectedMessage.raw_text.ilike(f"%{keyword.strip()}%"))
    query = (
        select(CollectedMessage)
        .where(*clauses)
        .order_by(func.coalesce(CollectedMessage.posted_at, CollectedMessage.collected_at).desc())
        .limit(limit)
    )
    async with AsyncSessionFactory() as session:
        return [_legacy_row(row) for row in (await session.scalars(query)).all()]


@app.get("/leaks")
async def telegram_leaks(limit: int = Query(default=1000, ge=1, le=1000)) -> list[dict[str, Any]]:
    """Primary Telegram dashboard API, combining both retained collectors."""
    core_rows = await _core_telegram_rows(limit=limit)
    try:
        legacy_rows = await _upstream_json(f"{LEGACY_TELEGRAM_API}/leaks?limit={limit}")
    except HTTPException:
        legacy_rows = []
    return [*core_rows, *legacy_rows][:limit]


@app.get("/search-leaks")
async def search_telegram_leaks(keyword: str = Query(min_length=1, max_length=200)) -> list[dict[str, Any]]:
    core_rows = await _core_telegram_rows(keyword=keyword)
    try:
        legacy_rows = await _upstream_json(
            f"{LEGACY_TELEGRAM_API}/search-leaks?{urlencode({'keyword': keyword})}"
        )
    except HTTPException:
        legacy_rows = []
    return [*core_rows, *legacy_rows]


@app.get("/channels")
async def telegram_channels() -> list[dict[str, Any]]:
    configured = [item.strip().lstrip("@") for item in os.getenv("TELEGRAM_CHANNELS", "").split(",") if item.strip()]
    core_channels = [{"id": f"core-{item}", "channel_id": item, "title": item, "handle": item, "pipeline": "redtraces-core"} for item in configured]
    try:
        legacy_channels = await _upstream_json(f"{LEGACY_TELEGRAM_API}/channels")
    except HTTPException:
        legacy_channels = []
    return [*core_channels, *legacy_channels]


@app.get("/accounts")
async def telegram_accounts() -> list[dict[str, Any]]:
    try:
        return await _upstream_json(f"{LEGACY_TELEGRAM_API}/accounts")
    except HTTPException:
        return [{"session_name": "redtraces-telegram", "status": "standby", "note": "Configure credentials and approved channels in .env."}]


@app.post("/add-channel")
async def add_telegram_channel(payload: dict[str, str]) -> Any:
    """Retain existing channel management through the legacy local monitor."""
    link = (payload.get("link") or "").strip()
    if not link:
        raise HTTPException(status_code=422, detail="link is required")
    return await _upstream_json(f"{LEGACY_TELEGRAM_API}/add-channel", {"link": link})


@app.get("/api/public/messages")
async def public_messages(
    platform: str = Query(default="telegram"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    """Read-only public gateway for locally running CTI collectors."""
    requested = platform.strip().lower()
    if requested == "telegram":
        items = await telegram_leaks(limit=limit)
    elif requested in PUBLIC_UPSTREAMS:
        upstream = await _upstream_json(PUBLIC_UPSTREAMS[requested])
        items = upstream.get("alerts", []) if requested == "forums" and isinstance(upstream, dict) else upstream
        items = items if isinstance(items, list) else []
    else:
        raise HTTPException(status_code=422, detail="platform must be telegram, twitter, facebook, instagram, or forums")
    return {"platform": requested, "items": items[:limit], "total": len(items)}


@app.get("/api/public/health")
async def public_health() -> dict[str, str]:
    result = {"telegram": "ok"}
    for platform, endpoint in PUBLIC_UPSTREAMS.items():
        try:
            await _upstream_json(endpoint)
            result[platform] = "ok"
        except HTTPException:
            result[platform] = "unavailable"
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/messages")
async def messages(
    platform: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters = []
    if platform:
        filters.append(CollectedMessage.platform == platform)

    count_query = select(func.count(CollectedMessage.id)).where(*filters)
    rows_query = (
        select(CollectedMessage)
        .where(*filters)
        .order_by(
            func.coalesce(
                CollectedMessage.posted_at, CollectedMessage.collected_at
            ).desc(),
            CollectedMessage.collected_at.desc(),
            CollectedMessage.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    async with AsyncSessionFactory() as session:
        total = int(await session.scalar(count_query) or 0)
        rows = list((await session.scalars(rows_query)).all())

    return {
        "items": [serialize_message(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/stats")
async def stats(platform: str | None = Query(default=None)) -> dict[str, int]:
    filters = []
    if platform:
        filters.append(CollectedMessage.platform == platform)
    last_hour = datetime.now(timezone.utc) - timedelta(hours=1)

    async with AsyncSessionFactory() as session:
        total = await session.scalar(
            select(func.count(CollectedMessage.id)).where(*filters)
        )
        recent = await session.scalar(
            select(func.count(CollectedMessage.id)).where(
                *filters, CollectedMessage.collected_at >= last_hour
            )
        )
        channels = await session.scalar(
            select(func.count(func.distinct(CollectedMessage.source))).where(*filters)
        )

    return {
        "total": int(total or 0),
        "last_hour": int(recent or 0),
        "unique_channels": int(channels or 0),
    }


@app.get("/api/layer2/metrics")
async def layer2_metrics() -> dict[str, Any]:
    """Expose non-content Layer 2 counters for the dashboard."""
    url = os.getenv("REDIS_URL", "").strip()
    empty: dict[str, Any] = {
        "available": False,
        "processed": 0,
        "accepted": 0,
        "rejected": 0,
        "languages": {},
        "detectors": {},
        "reasons": {},
    }
    if not url:
        return empty
    client = redis.from_url(url, decode_responses=True)
    try:
        raw = await client.hgetall("redtraces:layer2:metrics")
    except redis.RedisError:
        return empty
    finally:
        await client.aclose()

    result = {**empty, "available": True}
    for key, value in raw.items():
        count = int(value)
        if key.startswith("language:"):
            result["languages"][key.removeprefix("language:")] = count
        elif key.startswith("detector:"):
            result["detectors"][key.removeprefix("detector:")] = count
        elif key.startswith("reason:"):
            result["reasons"][key.removeprefix("reason:")] = count
        elif key in {"processed", "accepted", "rejected"}:
            result[key] = count
    return result


def _sqlite_items(query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if not STIX_STORE_PATH.is_file():
        return []
    connection = sqlite3.connect(STIX_STORE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        connection.close()


@app.get("/api/intelligence/iocs")
async def intelligence_iocs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Expose normalized STIX-store IOCs without returning large raw bundles."""
    rows = await asyncio.to_thread(
        _sqlite_items,
        """
        SELECT stix_id, ioc_value, ioc_type, source_id,
               first_seen, last_seen, sighting_count
        FROM iocs
        ORDER BY last_seen DESC, ioc_type, ioc_value
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    count_rows = await asyncio.to_thread(
        _sqlite_items, "SELECT COUNT(*) AS total FROM iocs"
    )
    return {
        "items": rows,
        "total": int(count_rows[0]["total"]) if count_rows else 0,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/artifacts")
async def artifacts() -> dict[str, list[dict[str, Any]]]:
    """List generated STIX, Sigma, and YARA artifacts from fixed output paths."""
    definitions = (
        ("stix", OUTPUT_DIRECTORY / "stix_bundles", "*.json", "validated bundle"),
        ("sigma", OUTPUT_DIRECTORY / "sigma_rules", "*.yml", "generated Sigma YAML"),
        ("yara", OUTPUT_DIRECTORY / "yara_rules", "*.yar", "compiled YARA file"),
    )
    items: list[dict[str, Any]] = []
    for artifact_type, directory, pattern, status in definitions:
        if not directory.is_dir():
            continue
        for path in directory.glob(pattern):
            details = path.stat()
            items.append(
                {
                    "name": path.name,
                    "artifact_type": artifact_type,
                    "size_bytes": details.st_size,
                    "modified_at": datetime.fromtimestamp(
                        details.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "status": status,
                }
            )
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"items": items}


@app.get("/api/siem/push-log")
async def siem_push_log(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, list[dict[str, Any]]]:
    """Return the local SIEM deployment audit without exposing credentials."""
    rows = await asyncio.to_thread(
        _sqlite_items,
        """
        SELECT id, attempted_at, siem_type, artifact_type, artifact_id,
               status, endpoint, response_code, message
        FROM siem_push_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"items": rows}


@app.get("/api/messages/stream")
async def message_stream(request: Request) -> StreamingResponse:
    """Stream newly collected Telegram rows using three-second DB polling."""

    async def events() -> AsyncIterator[str]:
        cursor_time = datetime.now(timezone.utc)
        cursor_id = None

        while not await request.is_disconnected():
            conditions = [
                CollectedMessage.platform == "telegram",
                CollectedMessage.collected_at >= cursor_time,
            ]
            if cursor_id is not None:
                conditions.append(
                    or_(
                        CollectedMessage.collected_at > cursor_time,
                        (
                            CollectedMessage.collected_at == cursor_time
                        )
                        & (CollectedMessage.id > cursor_id),
                    )
                )

            query = (
                select(CollectedMessage)
                .where(*conditions)
                .order_by(
                    CollectedMessage.collected_at.asc(),
                    CollectedMessage.id.asc(),
                )
            )
            async with AsyncSessionFactory() as session:
                rows = list((await session.scalars(query)).all())

            if rows:
                for row in rows:
                    cursor_time = row.collected_at
                    cursor_id = row.id
                    payload = json.dumps(serialize_message(row), separators=(",", ":"))
                    yield f"id: {row.id}\nevent: message\ndata: {payload}\n\n"
            else:
                yield ": heartbeat\n\n"

            await asyncio.sleep(3)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
