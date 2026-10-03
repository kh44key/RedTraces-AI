"""Continuously collect new Reddit submissions and top-level comments."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import praw
from dotenv import load_dotenv
from sqlalchemy import select

from common.db import AsyncSessionFactory, engine, init_db
from common.cti import cti_keywords, env_flag, matches_cti_keywords
from common.ioc import enrich_metadata
from common.models import CollectedMessage
from common.noise import evaluate_message

LOGGER = logging.getLogger(__name__)
REDDIT_URL = "https://www.reddit.com"


@dataclass(frozen=True)
class RedditItem:
    reddit_id: str
    source: str
    raw_text: str
    author: str | None
    url: str
    posted_at: datetime
    metadata: dict[str, Any]


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def configured_subreddits() -> list[str]:
    names = {
        name.strip()
        for name in os.getenv("REDDIT_SUBREDDITS", "").split(",")
        if name.strip()
    }
    return sorted(names)


def discover_subreddits(
    reddit: praw.Reddit, keywords: tuple[str, ...], maximum: int
) -> list[str]:
    discovered: set[str] = set()
    for keyword in keywords:
        try:
            for subreddit in reddit.subreddits.search(keyword, limit=10):
                name = str(subreddit.display_name)
                if name:
                    discovered.add(name)
                if len(discovered) >= maximum:
                    return sorted(discovered)
        except Exception:
            LOGGER.exception("Failed Reddit community discovery keyword=%s", keyword)
    return sorted(discovered)


def build_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=required_env("REDDIT_CLIENT_ID"),
        client_secret=required_env("REDDIT_CLIENT_SECRET"),
        user_agent=required_env("REDDIT_USER_AGENT"),
        check_for_async=False,
    )


def author_name(item: Any) -> str | None:
    return str(item.author) if item.author is not None else None


def fetch_items(reddit: praw.Reddit, subreddit_name: str) -> list[RedditItem]:
    """Fetch a bounded snapshot; PRAW is blocking, so call this in a thread."""
    subreddit = reddit.subreddit(subreddit_name)
    items: list[RedditItem] = []

    for submission in subreddit.new(limit=100):
        items.append(
            RedditItem(
                reddit_id=submission.id,
                source=subreddit_name,
                raw_text=f"{submission.title}\n\n{submission.selftext}".strip(),
                author=author_name(submission),
                url=f"{REDDIT_URL}{submission.permalink}",
                posted_at=datetime.fromtimestamp(
                    submission.created_utc, tz=timezone.utc
                ),
                metadata={
                    "reddit_id": submission.id,
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                },
            )
        )

    for comment in subreddit.comments(limit=100):
        if not comment.parent_id.startswith("t3_"):
            continue
        items.append(
            RedditItem(
                reddit_id=comment.id,
                source=subreddit_name,
                raw_text=comment.body,
                author=author_name(comment),
                url=f"{REDDIT_URL}{comment.permalink}",
                posted_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
                metadata={"reddit_id": comment.id, "score": comment.score},
            )
        )

    return items


async def load_recent_reddit_ids() -> set[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    query = select(CollectedMessage.metadata_["reddit_id"].astext).where(
        CollectedMessage.platform == "reddit",
        CollectedMessage.collected_at >= cutoff,
    )
    async with AsyncSessionFactory() as session:
        return {reddit_id for reddit_id in await session.scalars(query) if reddit_id}


async def insert_new_items(
    items: list[RedditItem], seen_reddit_ids: set[str]
) -> None:
    fresh_items: list[RedditItem] = []
    batch_ids: set[str] = set()
    for item in items:
        if item.reddit_id not in seen_reddit_ids and item.reddit_id not in batch_ids:
            fresh_items.append(item)
            batch_ids.add(item.reddit_id)

    if not fresh_items:
        return

    accepted_items: list[RedditItem] = []
    enriched_metadata: list[dict[str, Any]] = []
    for item in fresh_items:
        noise = await evaluate_message("reddit", item.source, item.raw_text)
        if not noise.accepted:
            LOGGER.info(
                "Filtered Reddit item reddit_id=%s subreddit=%s reason=%s language=%s",
                item.reddit_id,
                item.source,
                noise.reason,
                noise.language,
            )
            seen_reddit_ids.add(item.reddit_id)
            continue
        accepted_items.append(item)
        enriched_metadata.append(
            enrich_metadata(
                {**item.metadata, "noise": noise.metadata()},
                item.raw_text,
            )
        )
    if not accepted_items:
        return

    async with AsyncSessionFactory() as session:
        session.add_all(
            [
                CollectedMessage(
                    platform="reddit",
                    source=item.source,
                    raw_text=item.raw_text,
                    author=item.author,
                    url=item.url,
                    posted_at=item.posted_at,
                    metadata_=metadata,
                    attachments=[],
                )
                for item, metadata in zip(accepted_items, enriched_metadata)
            ]
        )
        await session.commit()

    seen_reddit_ids.update(item.reddit_id for item in accepted_items)
    for item, metadata in zip(accepted_items, enriched_metadata):
        LOGGER.info(
            "Inserted Reddit item reddit_id=%s subreddit=%s url=%s fetched_iocs=%d",
            item.reddit_id,
            item.source,
            item.url,
            metadata["ioc_count"],
        )


async def run() -> None:
    load_dotenv()
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    if poll_interval <= 0:
        raise RuntimeError("POLL_INTERVAL_SECONDS must be greater than zero")

    subreddits = configured_subreddits()
    reddit = build_reddit_client()
    keywords = cti_keywords()
    if env_flag("REDDIT_DISCOVERY_ENABLED", True):
        maximum = int(os.getenv("REDDIT_MAX_SUBREDDITS", "20"))
        discovered = await asyncio.to_thread(
            discover_subreddits, reddit, keywords, maximum
        )
        subreddits = sorted(set(subreddits).union(discovered))[:maximum]
        LOGGER.info("Discovered Reddit communities: %s", ", ".join(discovered))
    if not subreddits:
        raise RuntimeError(
            "No subreddits configured or discovered; set REDDIT_SUBREDDITS"
        )
    await init_db()
    seen_reddit_ids = await load_recent_reddit_ids()
    LOGGER.info(
        "Starting Reddit collector for %s; loaded %d recently seen IDs",
        ", ".join(subreddits),
        len(seen_reddit_ids),
    )

    try:
        while True:
            for subreddit_name in subreddits:
                try:
                    items = await asyncio.to_thread(
                        fetch_items, reddit, subreddit_name
                    )
                    if env_flag("CTI_FILTER_CONTENT", True):
                        items = [
                            item
                            for item in items
                            if matches_cti_keywords(
                                (item.raw_text, item.source), keywords
                            )
                        ]
                    await insert_new_items(items, seen_reddit_ids)
                except Exception:
                    LOGGER.exception(
                        "Failed to poll subreddit=%s; retrying next cycle",
                        subreddit_name,
                    )
            await asyncio.sleep(poll_interval)
    finally:
        await asyncio.to_thread(reddit.close)
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
