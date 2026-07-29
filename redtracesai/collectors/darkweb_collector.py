"""Poll known onion forums through Tor and persist parsed forum posts."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import requests
import structlog
from dotenv import load_dotenv
from requests import Response, Session
from sqlalchemy import select
from stem.control import Controller

from common.cti import cti_keywords, env_flag, matches_cti_keywords
from common.db import AsyncSessionFactory, engine, init_db
from common.ioc import enrich_metadata
from common.models import CollectedMessage
from common.noise import evaluate_message

log = structlog.get_logger(__name__)
InsertFunction = Callable[[str, str, dict[str, Any]], Awaitable[bool]]


class DarkWebAdapter(ABC):
    """Base interface for site-specific forum parsers."""

    @abstractmethod
    def parse(self, html: str) -> list[dict[str, Any]]:
        """Return normalized forum-post dictionaries from a page."""


class _ExampleForumHTMLParser(HTMLParser):
    """Parser for the documented placeholder markup used by the example."""

    def __init__(self, forum_name: str) -> None:
        super().__init__()
        self.forum_name = forum_name
        self.posts: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.capture: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "article" and "forum-post" in classes:
            self.current = {
                "forum_name": self.forum_name,
                "url": attributes.get("data-url"),
                "posted_at": attributes.get("data-posted-at"),
                "author": None,
                "thread_title": None,
                "body": "",
            }
        elif self.current is not None:
            if "thread-title" in classes:
                self.capture = "thread_title"
            elif "author" in classes:
                self.capture = "author"
            elif "post-body" in classes:
                self.capture = "body"

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture is not None:
            self.current[self.capture] = (
                f"{self.current.get(self.capture) or ''}{data}"
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self.current is not None:
            for field in ("body", "author", "thread_title"):
                value = self.current.get(field)
                if isinstance(value, str):
                    self.current[field] = value.strip() or None
            self.current["body"] = self.current["body"] or ""
            self.posts.append(self.current)
            self.current = None
            self.capture = None
        elif self.capture is not None and tag in {"h1", "h2", "h3", "span", "div"}:
            self.capture = None


class ExampleForumAdapter(DarkWebAdapter):
    """Example adapter; replace its placeholder selectors per real forum."""

    def __init__(self, forum_name: str) -> None:
        self.forum_name = forum_name

    def parse(self, html: str) -> list[dict[str, Any]]:
        """Parse ``article.forum-post`` placeholder elements.

        Expected attributes/classes are ``data-url``, ``data-posted-at``,
        ``.thread-title``, ``.author``, and ``.post-body``.
        """
        parser = _ExampleForumHTMLParser(self.forum_name)
        parser.feed(html)
        return parser.posts


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def internal_onion_links(html: str, current_url: str, domain: str) -> list[str]:
    parser = _LinkParser()
    parser.feed(html)
    links: list[str] = []
    for href in parser.links:
        absolute, _ = urldefrag(urljoin(current_url, href))
        parsed = urlparse(absolute)
        if (
            parsed.scheme in {"http", "https"}
            and parsed.hostname == domain
            and absolute not in links
        ):
            links.append(absolute)
    return links


# Register domain-specific adapters here as real site selectors are added.
ADAPTERS: dict[str, type[DarkWebAdapter]] = {}


def adapter_for_target(target: str) -> DarkWebAdapter:
    domain = target_domain(target)
    adapter_class = ADAPTERS.get(domain, ExampleForumAdapter)
    return adapter_class(domain)  # type: ignore[call-arg]


def configured_targets() -> list[str]:
    targets = [
        value.strip()
        for value in os.getenv("DARKWEB_TARGETS", "").split(",")
        if value.strip()
    ]
    if not targets:
        raise RuntimeError("DARKWEB_TARGETS must contain at least one onion URL")
    for target in targets:
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not (
            parsed.hostname and parsed.hostname.endswith(".onion")
        ):
            raise RuntimeError(f"DARKWEB_TARGETS contains an invalid onion URL: {target}")
    return targets


def target_domain(target: str) -> str:
    domain = urlparse(target).hostname
    if not domain:
        raise ValueError(f"Target has no hostname: {target}")
    return domain


def connect_to_tor_control() -> None:
    host = os.getenv("TOR_CONTROL_HOST", "tor")
    port = int(os.getenv("TOR_CONTROL_PORT", "9051"))
    password = os.getenv("TOR_CONTROL_PASSWORD", "change-me")
    attempts = int(os.getenv("DARKWEB_RETRY_ATTEMPTS", "4"))

    for attempt in range(attempts):
        try:
            with Controller.from_port(address=host, port=port) as controller:
                controller.authenticate(password=password)
                bootstrap = controller.get_info("status/bootstrap-phase", "")
                log.info("tor_control_connected", bootstrap=bootstrap)
                return
        except Exception as error:
            if attempt == attempts - 1:
                raise RuntimeError("Unable to connect to Tor control port") from error
            delay = min(2**attempt, 30)
            log.warning(
                "tor_control_retry",
                attempt=attempt + 1,
                delay_seconds=delay,
                error=str(error),
            )
            time.sleep(delay)


def build_http_session() -> Session:
    proxy = os.getenv("TOR_SOCKS_PROXY", "socks5h://tor:9050")
    session = requests.Session()
    session.proxies.update({"http": proxy, "https": proxy})
    session.headers["User-Agent"] = os.getenv(
        "DARKWEB_USER_AGENT", "redtracesai-research/0.1"
    )
    return session


def fetch_with_retry(session: Session, target: str) -> Response:
    timeout = float(os.getenv("DARKWEB_REQUEST_TIMEOUT_SECONDS", "45"))
    attempts = int(os.getenv("DARKWEB_RETRY_ATTEMPTS", "4"))
    last_error: requests.RequestException | None = None

    for attempt in range(attempts):
        try:
            response = session.get(target, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt == attempts - 1:
                break
            delay = min(2**attempt, 60)
            log.warning(
                "darkweb_fetch_retry",
                target=target,
                attempt=attempt + 1,
                delay_seconds=delay,
                error=str(error),
            )
            time.sleep(delay)

    raise RuntimeError(f"Failed to fetch {target}") from last_error


def parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        log.warning("darkweb_timestamp_invalid", value=value)
        return None


async def insert_post(source: str, target: str, post: dict[str, Any]) -> bool:
    post_url = urljoin(target, post["url"]) if post.get("url") else None
    analysis_text = " ".join(
        (
            str(post.get("thread_title") or ""),
            str(post.get("body") or ""),
        )
    )
    noise = await evaluate_message("darkweb", source, analysis_text)
    if not noise.accepted:
        log.info(
            "darkweb_post_filtered",
            source=source,
            url=post_url,
            reason=noise.reason,
            language=noise.language,
        )
        return False
    if post_url:
        duplicate_query = (
            select(CollectedMessage.id)
            .where(
                CollectedMessage.platform == "darkweb",
                CollectedMessage.source == source,
                CollectedMessage.url == post_url,
            )
            .limit(1)
        )
        async with AsyncSessionFactory() as session:
            if await session.scalar(duplicate_query) is not None:
                return False

    row = CollectedMessage(
        platform="darkweb",
        source=source,
        raw_text=str(post.get("body") or ""),
        author=str(post["author"]) if post.get("author") else None,
        url=post_url,
        posted_at=parse_timestamp(post.get("posted_at")),
        metadata_=enrich_metadata(
            {
                "forum_name": str(post.get("forum_name") or source),
                "thread_title": str(post.get("thread_title") or ""),
                "noise": noise.metadata(),
            },
            analysis_text,
        ),
        attachments=[],
    )
    async with AsyncSessionFactory() as session:
        session.add(row)
        await session.commit()

    log.info(
        "darkweb_post_inserted",
        source=source,
        url=post_url,
        author=row.author,
        fetched_iocs=row.metadata_["ioc_count"],
    )
    return True


async def process_target(
    session: Session,
    target: str,
    adapter: DarkWebAdapter,
    insert_function: InsertFunction = insert_post,
) -> int:
    """Fetch, parse, and insert one target; dependencies are injectable for tests."""
    response = await asyncio.to_thread(fetch_with_retry, session, target)
    posts = adapter.parse(response.text)
    source = target_domain(target)
    inserted = 0
    for post in posts:
        inserted += int(await insert_function(source, target, post))
    log.info(
        "darkweb_target_processed",
        target=target,
        parsed_posts=len(posts),
        inserted_posts=inserted,
    )
    return inserted


async def crawl_target(
    session: Session,
    seed: str,
    adapter: DarkWebAdapter,
    insert_function: InsertFunction = insert_post,
) -> int:
    """Crawl a bounded set of same-onion pages from an approved seed URL."""
    maximum_depth = int(os.getenv("DARKWEB_MAX_DEPTH", "2"))
    maximum_pages = int(os.getenv("DARKWEB_MAX_PAGES_PER_TARGET", "100"))
    crawl_delay = float(os.getenv("DARKWEB_CRAWL_DELAY_SECONDS", "10"))
    keywords = cti_keywords()
    source = target_domain(seed)
    queue: list[tuple[str, int]] = [(seed, 0)]
    visited: set[str] = set()
    inserted = 0

    while queue and len(visited) < maximum_pages:
        page_url, depth = queue.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)
        try:
            response = await asyncio.to_thread(fetch_with_retry, session, page_url)
            posts = adapter.parse(response.text)
            for post in posts:
                if env_flag("CTI_FILTER_CONTENT", True) and not matches_cti_keywords(
                    (
                        post.get("body"),
                        post.get("thread_title"),
                        post.get("forum_name"),
                    ),
                    keywords,
                ):
                    continue
                inserted += int(await insert_function(source, page_url, post))

            if depth < maximum_depth:
                for link in internal_onion_links(response.text, page_url, source):
                    if link not in visited and all(link != queued[0] for queued in queue):
                        queue.append((link, depth + 1))
        except Exception:
            log.exception(
                "darkweb_page_failed",
                target=seed,
                page_url=page_url,
                depth=depth,
            )

        if queue and len(visited) < maximum_pages:
            await asyncio.sleep(crawl_delay)

    log.info(
        "darkweb_crawl_complete",
        target=seed,
        pages_visited=len(visited),
        inserted_posts=inserted,
    )
    return inserted


async def run() -> None:
    load_dotenv()
    targets = configured_targets()
    crawl_delay = float(os.getenv("DARKWEB_CRAWL_DELAY_SECONDS", "10"))
    poll_interval = float(os.getenv("DARKWEB_POLL_INTERVAL_SECONDS", "300"))
    if crawl_delay < 0 or poll_interval <= 0:
        raise RuntimeError("Crawl delay must be non-negative and poll interval positive")

    await init_db()
    await asyncio.to_thread(connect_to_tor_control)
    session = build_http_session()
    try:
        while True:
            for index, target in enumerate(targets):
                try:
                    await crawl_target(session, target, adapter_for_target(target))
                except Exception:
                    log.exception("darkweb_target_failed", target=target)
                if index < len(targets) - 1:
                    await asyncio.sleep(crawl_delay)
            await asyncio.sleep(poll_interval)
    finally:
        session.close()
        await engine.dispose()


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
