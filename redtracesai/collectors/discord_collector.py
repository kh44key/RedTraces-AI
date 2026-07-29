"""Collect messages from explicitly configured Discord channels."""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any

import discord
import structlog
from dotenv import load_dotenv
from sqlalchemy import select

from common.cti import env_flag, matches_cti_keywords
from common.db import AsyncSessionFactory, engine, init_db
from common.ioc import enrich_metadata
from common.models import CollectedMessage
from common.noise import evaluate_message

MAX_HASH_SIZE = 10 * 1024 * 1024
log = structlog.get_logger(__name__)
insert_lock = asyncio.Lock()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def configured_channel_ids() -> set[int]:
    raw_values = [
        value.strip()
        for value in os.getenv("DISCORD_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]
    if not raw_values:
        raise RuntimeError(
            "DISCORD_CHANNEL_IDS must contain at least one Discord channel ID"
        )
    try:
        return {int(value) for value in raw_values}
    except ValueError as error:
        raise RuntimeError("DISCORD_CHANNEL_IDS must contain only numeric IDs") from error


def source_name(message: discord.Message) -> str:
    guild_name = message.guild.name if message.guild else "direct"
    channel_name = getattr(message.channel, "name", str(message.channel.id))
    return f"{guild_name}/{channel_name}"


async def already_collected(message_id: int) -> bool:
    query = (
        select(CollectedMessage.id)
        .where(
            CollectedMessage.platform == "discord",
            CollectedMessage.metadata_["message_id"].as_string() == str(message_id),
        )
        .limit(1)
    )
    async with AsyncSessionFactory() as session:
        return await session.scalar(query) is not None


async def attachment_metadata(
    attachments: list[discord.Attachment],
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for attachment in attachments:
        item = {
            "filename": attachment.filename,
            "type": attachment.content_type or "application/octet-stream",
        }
        if attachment.size <= MAX_HASH_SIZE:
            try:
                payload = await attachment.read()
                item["sha256"] = hashlib.sha256(payload).hexdigest()
            except discord.HTTPException as error:
                log.warning(
                    "discord_attachment_download_failed",
                    attachment_id=attachment.id,
                    filename=attachment.filename,
                    error=str(error),
                )
        else:
            log.info(
                "discord_attachment_hash_skipped",
                attachment_id=attachment.id,
                filename=attachment.filename,
                size_bytes=attachment.size,
            )
        results.append(item)
    return results


async def collect_message(message: discord.Message) -> bool:
    if message.author.bot and not env_flag("DISCORD_INCLUDE_BOTS", False):
        return False
    if env_flag("CTI_FILTER_CONTENT", True) and not matches_cti_keywords(
        (
            message.content,
            source_name(message),
            *(attachment.filename for attachment in message.attachments),
        )
    ):
        return False
    source = source_name(message)
    noise = await evaluate_message(
        "discord",
        source,
        message.content,
        has_attachments=bool(message.attachments),
    )
    if not noise.accepted:
        log.info(
            "discord_message_filtered",
            source=source,
            message_id=str(message.id),
            reason=noise.reason,
            language=noise.language,
        )
        return False

    async with insert_lock:
        if await already_collected(message.id):
            return False

        metadata = enrich_metadata(
            {
                # Discord snowflakes exceed JavaScript's safe integer range,
                # so identifiers are stored as strings in JSON.
                "message_id": str(message.id),
                "channel_id": str(message.channel.id),
                "guild_id": str(message.guild.id) if message.guild else None,
                "noise": noise.metadata(),
            },
            message.content,
        )
        row = CollectedMessage(
            platform="discord",
            source=source,
            raw_text=message.content or "",
            author=str(message.author),
            url=message.jump_url,
            posted_at=message.created_at,
            metadata_=metadata,
            attachments=await attachment_metadata(message.attachments),
        )
        async with AsyncSessionFactory() as session:
            session.add(row)
            await session.commit()

        log.info(
            "discord_message_inserted",
            source=source,
            message_id=str(message.id),
            author=row.author,
            url=row.url,
            fetched_iocs=metadata["ioc_count"],
        )
        return True


class DiscordCollector(discord.Client):
    def __init__(self, channel_ids: set[int], backfill_limit: int) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.channel_ids = channel_ids
        self.backfill_limit = backfill_limit
        self.backfill_complete = False

    async def on_ready(self) -> None:
        log.info(
            "discord_collector_ready",
            bot_user=str(self.user),
            channel_ids=sorted(self.channel_ids),
        )
        if self.backfill_complete:
            return
        self.backfill_complete = True

        for channel_id in self.channel_ids:
            try:
                channel = self.get_channel(channel_id) or await self.fetch_channel(
                    channel_id
                )
                history = getattr(channel, "history", None)
                if history is None:
                    log.warning(
                        "discord_channel_history_unavailable",
                        channel_id=channel_id,
                    )
                    continue
                messages = [
                    message
                    async for message in history(limit=self.backfill_limit)
                ]
                for message in reversed(messages):
                    await collect_message(message)
                log.info(
                    "discord_channel_backfill_complete",
                    channel_id=channel_id,
                    messages_examined=len(messages),
                )
            except Exception:
                log.exception(
                    "discord_channel_backfill_failed",
                    channel_id=channel_id,
                )

    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id not in self.channel_ids:
            return
        try:
            await collect_message(message)
        except Exception:
            log.exception(
                "discord_message_failed",
                channel_id=message.channel.id,
                message_id=str(message.id),
            )


async def run() -> None:
    load_dotenv()
    token = required_env("DISCORD_BOT_TOKEN")
    channel_ids = configured_channel_ids()
    backfill_limit = int(os.getenv("DISCORD_BACKFILL_LIMIT", "100"))
    if not 0 <= backfill_limit <= 1000:
        raise RuntimeError("DISCORD_BACKFILL_LIMIT must be between 0 and 1000")

    await init_db()
    client = DiscordCollector(channel_ids, backfill_limit)
    try:
        await client.start(token)
    finally:
        if not client.is_closed():
            await client.close()
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
