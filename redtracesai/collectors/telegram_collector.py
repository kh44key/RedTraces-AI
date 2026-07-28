"""Collect Telegram channel messages through Telethon's MTProto client."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import structlog
from dotenv import load_dotenv
from sqlalchemy import select
from telethon import TelegramClient, events
from telethon import functions
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.types import Channel, PeerChannel

from common.cti import cti_keywords, env_flag, matches_cti_keywords
from common.db import AsyncSessionFactory, engine, init_db
from common.ioc import enrich_metadata
from common.models import CollectedMessage

MAX_HASH_SIZE = 10 * 1024 * 1024
T = TypeVar("T")
log = structlog.get_logger(__name__)
insert_lock = asyncio.Lock()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def configured_channels() -> list[str]:
    channels: list[str] = []
    for value in os.getenv("TELEGRAM_CHANNELS", "").split(","):
        username = value.strip().lstrip("@")
        if username and username not in channels:
            channels.append(username)
    return channels


async def discover_public_channels(
    client: TelegramClient, keywords: tuple[str, ...], maximum: int
) -> list[str]:
    """Discover a bounded set of public channels by CTI keyword."""
    discovered: list[str] = []
    for keyword in keywords:
        result = await with_flood_backoff(
            lambda keyword=keyword: client(
                functions.contacts.SearchRequest(q=keyword, limit=20)
            ),
            f"discover_channels:{keyword}",
        )
        for chat in result.chats:
            if (
                not isinstance(chat, Channel)
                or not chat.username
                or chat.username in discovered
            ):
                continue
            if not (getattr(chat, "broadcast", False) or getattr(chat, "megagroup", False)):
                continue
            discovered.append(chat.username)
            log.info(
                "telegram_channel_discovered",
                channel=chat.username,
                keyword=keyword,
            )
            if len(discovered) >= maximum:
                return discovered
    return discovered


async def join_public_channel(client: TelegramClient, channel: Any) -> None:
    if not env_flag("TELEGRAM_AUTO_JOIN", True):
        return
    try:
        await with_flood_backoff(
            lambda: client(functions.channels.JoinChannelRequest(channel)),
            f"join_channel:{getattr(channel, 'username', channel)}",
        )
        log.info(
            "telegram_channel_joined",
            channel=getattr(channel, "username", str(channel)),
        )
    except UserAlreadyParticipantError:
        log.info(
            "telegram_channel_already_joined",
            channel=getattr(channel, "username", str(channel)),
        )


async def with_flood_backoff(
    operation: Callable[[], Awaitable[T]], operation_name: str
) -> T:
    """Retry a Telethon operation using server and exponential wait times."""
    attempt = 0
    while True:
        try:
            return await operation()
        except FloodWaitError as error:
            delay = max(error.seconds, min(2**attempt, 300))
            attempt += 1
            log.warning(
                "telegram_flood_wait",
                operation=operation_name,
                delay_seconds=delay,
                attempt=attempt,
            )
            await asyncio.sleep(delay)


def channel_id_from_message(message: Any) -> int | None:
    peer = getattr(message, "peer_id", None)
    return peer.channel_id if isinstance(peer, PeerChannel) else None


async def attachment_metadata(message: Any) -> list[dict[str, str]]:
    if message.media is None:
        return []

    telegram_file = message.file
    extension = getattr(telegram_file, "ext", "") or ""
    filename = (
        getattr(telegram_file, "name", None)
        or f"telegram-{message.id}{extension}"
    )
    media_type = (
        getattr(telegram_file, "mime_type", None)
        or type(message.media).__name__
    )
    attachment = {"filename": filename, "type": media_type}
    size = getattr(telegram_file, "size", None)

    if size is not None and size <= MAX_HASH_SIZE:
        payload = await with_flood_backoff(
            lambda: message.download_media(file=bytes),
            f"download_media:{message.id}",
        )
        if payload is not None:
            attachment["sha256"] = hashlib.sha256(payload).hexdigest()
    elif size is not None:
        log.info(
            "telegram_media_hash_skipped",
            message_id=message.id,
            filename=filename,
            size_bytes=size,
        )
    else:
        log.info(
            "telegram_media_hash_skipped",
            message_id=message.id,
            filename=filename,
            reason="unknown_size",
        )

    return [attachment]


async def already_collected(source: str, message_id: int) -> bool:
    query = (
        select(CollectedMessage.id)
        .where(
            CollectedMessage.platform == "telegram",
            CollectedMessage.source == source,
            CollectedMessage.metadata_["message_id"].as_integer() == message_id,
        )
        .limit(1)
    )
    async with AsyncSessionFactory() as session:
        return await session.scalar(query) is not None


async def collect_message(message: Any, source: str) -> None:
    if message.id is None:
        return
    if env_flag("CTI_FILTER_CONTENT", True) and not matches_cti_keywords(
        (message.raw_text, source)
    ):
        return

    # The lock prevents a live event and startup backfill from racing each
    # other between the existence check and commit.
    async with insert_lock:
        if await already_collected(source, message.id):
            return

        sender = await with_flood_backoff(
            message.get_sender, f"get_sender:{source}:{message.id}"
        )
        sender_id = getattr(sender, "id", None)
        author = getattr(sender, "username", None)
        if not author and sender_id is not None:
            author = str(sender_id)

        attachments = await attachment_metadata(message)
        row = CollectedMessage(
            platform="telegram",
            source=source,
            raw_text=message.raw_text or "",
            author=author,
            url=f"https://t.me/{source}/{message.id}",
            posted_at=message.date,
            metadata_=enrich_metadata(
                {
                    "message_id": message.id,
                    "views": message.views,
                    "forwards": message.forwards,
                },
                message.raw_text,
            ),
            attachments=attachments,
        )
        async with AsyncSessionFactory() as session:
            session.add(row)
            await session.commit()

        log.info(
            "telegram_message_inserted",
            source=source,
            message_id=message.id,
            author=author,
            url=row.url,
            fetched_iocs=row.metadata_["ioc_count"],
        )


async def run() -> None:
    load_dotenv()
    api_id = int(required_env("TELEGRAM_API_ID"))
    api_hash = required_env("TELEGRAM_API_HASH")
    channels = configured_channels()
    session_path = Path(
        os.getenv("TELEGRAM_SESSION", "sessions/redtracesai")
    )
    session_path.parent.mkdir(parents=True, exist_ok=True)

    await init_db()
    client = TelegramClient(str(session_path), api_id, api_hash)
    await with_flood_backoff(client.start, "client_start")

    try:
        if env_flag("TELEGRAM_DISCOVERY_ENABLED", True):
            maximum = int(os.getenv("TELEGRAM_MAX_CHANNELS", "20"))
            discovered = await discover_public_channels(
                client, cti_keywords(), maximum
            )
            channels = list(dict.fromkeys([*channels, *discovered]))[:maximum]
            log.info("telegram_discovery_complete", channels=discovered)
        if not channels:
            raise RuntimeError(
                "No Telegram channels configured or discovered; set TELEGRAM_CHANNELS"
            )

        entities: list[Any] = []
        source_by_channel_id: dict[int, str] = {}
        for username in channels:
            entity = await with_flood_backoff(
                lambda username=username: client.get_entity(username),
                f"resolve_channel:{username}",
            )
            try:
                await join_public_channel(client, entity)
            except Exception:
                log.exception("telegram_channel_join_failed", channel=username)
            entities.append(entity)
            source_by_channel_id[entity.id] = username

        async def handle_new_message(event: events.NewMessage.Event) -> None:
            channel_id = channel_id_from_message(event.message)
            source = source_by_channel_id.get(channel_id)
            if source is None:
                return
            try:
                await collect_message(event.message, source)
            except Exception:
                log.exception(
                    "telegram_message_failed",
                    source=source,
                    message_id=event.message.id,
                )

        client.add_event_handler(handle_new_message, events.NewMessage(chats=entities))

        for entity in entities:
            source = source_by_channel_id[entity.id]

            async def backfill() -> None:
                async for message in client.iter_messages(entity, limit=100):
                    await collect_message(message, source)

            await with_flood_backoff(backfill, f"backfill:{source}")

        log.info("telegram_live_listener_started", channels=channels)
        await client.run_until_disconnected()
    finally:
        await client.disconnect()
        await engine.dispose()


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
