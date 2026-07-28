"""FastAPI application serving collected-message history and live updates."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from common.db import AsyncSessionFactory, engine, init_db
from common.models import CollectedMessage


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
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
