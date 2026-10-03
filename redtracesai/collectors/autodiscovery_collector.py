"""Discover public CTI reports through pluggable search providers."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
import structlog
from dotenv import load_dotenv
from requests import Session
from sqlalchemy import select

from common.cti import env_flag, matches_cti_keywords
from common.db import AsyncSessionFactory, engine, init_db
from common.ioc import enrich_metadata
from common.models import CollectedMessage
from common.noise import evaluate_message

GOOGLE_CSE_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"
SERPER_SEARCH_ENDPOINT = "https://google.serper.dev/search"
DEFAULT_QUERIES = (
    '("ransomware" OR "malware") '
    '("indicators of compromise" OR "IOC") filetype:pdf'
    "||"
    '("CVE" OR "zero-day") ("incident response" OR "threat report")'
    "||"
    '("phishing" OR "infostealer") ("C2" OR "SHA256")'
)
log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DiscoveryResult:
    title: str
    snippet: str
    url: str
    display_link: str
    rank: int


class DiscoveryProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, limit: int) -> list[DiscoveryResult]:
        """Return normalized public search results."""


class GoogleCSEProvider(DiscoveryProvider):
    """Google Programmable Search JSON API provider for existing customers."""

    name = "google_cse"

    def __init__(
        self,
        api_key: str,
        search_engine_id: str,
        session: Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.session = session or requests.Session()
        self.timeout = float(os.getenv("AUTODISCOVERY_REQUEST_TIMEOUT_SECONDS", "30"))
        self.retry_attempts = int(os.getenv("AUTODISCOVERY_RETRY_ATTEMPTS", "4"))

    def _request_page(
        self, query: str, start: int, number: int
    ) -> dict[str, Any]:
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.get(
                    GOOGLE_CSE_ENDPOINT,
                    params={
                        "key": self.api_key,
                        "cx": self.search_engine_id,
                        "q": query,
                        "start": start,
                        "num": number,
                        "safe": "active",
                        "filter": "1",
                    },
                    timeout=self.timeout,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                if 400 <= response.status_code < 500:
                    raise RuntimeError(
                        f"Google CSE rejected the request with HTTP "
                        f"{response.status_code}"
                    )
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except (requests.RequestException, ValueError) as error:
                if attempt == self.retry_attempts - 1:
                    raise RuntimeError("Google CSE request failed") from error
                delay = min(2**attempt, 30)
                log.warning(
                    "autodiscovery_search_retry",
                    provider=self.name,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    error=str(error),
                )
                time.sleep(delay)
        return {}

    def search(self, query: str, limit: int) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        start = 1
        while len(results) < limit:
            page_size = min(10, limit - len(results))
            payload = self._request_page(query, start, page_size)
            items = payload.get("items")
            if not isinstance(items, list) or not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                link = str(item.get("link") or "").strip()
                parsed = urlparse(link)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    continue
                results.append(
                    DiscoveryResult(
                        title=str(item.get("title") or "").strip(),
                        snippet=str(item.get("snippet") or "").strip(),
                        url=link,
                        display_link=str(
                            item.get("displayLink") or parsed.hostname
                        ).strip(),
                        rank=len(results) + 1,
                    )
                )
                if len(results) >= limit:
                    break
            if len(items) < page_size:
                break
            start += len(items)
        return results


class SerperProvider(DiscoveryProvider):
    """Serper Google Search API provider for public CTI result discovery."""

    name = "serper"

    def __init__(self, api_key: str, session: Session | None = None) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = float(os.getenv("AUTODISCOVERY_REQUEST_TIMEOUT_SECONDS", "30"))
        self.retry_attempts = int(os.getenv("AUTODISCOVERY_RETRY_ATTEMPTS", "4"))

    def _request_page(self, query: str, number: int) -> dict[str, Any]:
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.post(
                    SERPER_SEARCH_ENDPOINT,
                    headers={"X-API-KEY": self.api_key},
                    json={"q": query, "num": number, "autocorrect": False},
                    timeout=self.timeout,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                if 400 <= response.status_code < 500:
                    raise RuntimeError(
                        f"Serper rejected the request with HTTP {response.status_code}"
                    )
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except (requests.RequestException, ValueError) as error:
                if attempt == self.retry_attempts - 1:
                    raise RuntimeError("Serper request failed") from error
                delay = min(2**attempt, 30)
                log.warning(
                    "autodiscovery_search_retry",
                    provider=self.name,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    error=str(error),
                )
                time.sleep(delay)
        return {}

    def search(self, query: str, limit: int) -> list[DiscoveryResult]:
        payload = self._request_page(query, limit)
        items = payload.get("organic")
        if not isinstance(items, list):
            return []

        results: list[DiscoveryResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            link = str(item.get("link") or "").strip()
            parsed = urlparse(link)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            results.append(
                DiscoveryResult(
                    title=str(item.get("title") or "").strip(),
                    snippet=str(item.get("snippet") or "").strip(),
                    url=link,
                    display_link=parsed.hostname,
                    rank=int(item.get("position") or len(results) + 1),
                )
            )
            if len(results) >= limit:
                break
        return results


InsertFunction = Callable[[str, DiscoveryResult], Awaitable[bool]]


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def configured_queries() -> list[str]:
    raw = os.getenv("AUTODISCOVERY_QUERIES", "").strip() or DEFAULT_QUERIES
    queries = list(
        dict.fromkeys(query.strip() for query in raw.split("||") if query.strip())
    )
    if not queries:
        raise RuntimeError("AUTODISCOVERY_QUERIES must contain at least one query")
    return queries


def build_provider() -> DiscoveryProvider:
    provider_name = os.getenv("AUTODISCOVERY_PROVIDER", "google_cse").strip().lower()
    if provider_name == "google_cse":
        return GoogleCSEProvider(
            required_env("GOOGLE_CSE_API_KEY"),
            required_env("GOOGLE_CSE_ID"),
        )
    if provider_name == "serper":
        return SerperProvider(required_env("SERPER_API_KEY"))
    raise RuntimeError(
        "Unsupported AUTODISCOVERY_PROVIDER; supported: google_cse, serper"
    )


async def insert_result(query: str, result: DiscoveryResult) -> bool:
    duplicate_query = (
        select(CollectedMessage.id)
        .where(
            CollectedMessage.platform == "autodiscovery",
            CollectedMessage.url == result.url,
        )
        .limit(1)
    )
    async with AsyncSessionFactory() as session:
        if await session.scalar(duplicate_query) is not None:
            return False

    raw_text = "\n\n".join(
        value for value in (result.title, result.snippet) if value
    )
    source = urlparse(result.url).hostname or result.display_link
    if env_flag("CTI_FILTER_CONTENT", True) and not matches_cti_keywords(
        (raw_text, query, source)
    ):
        return False

    noise = await evaluate_message("autodiscovery", source, raw_text)
    if not noise.accepted:
        log.info(
            "autodiscovery_result_filtered",
            source=source,
            url=result.url,
            reason=noise.reason,
            language=noise.language,
        )
        return False

    metadata = enrich_metadata(
        {
            "provider": "google_cse",
            "search_query": query,
            "result_rank": result.rank,
            "display_link": result.display_link,
            "noise": noise.metadata(),
        },
        raw_text,
    )
    row = CollectedMessage(
        platform="autodiscovery",
        source=source,
        raw_text=raw_text,
        author=None,
        url=result.url,
        posted_at=None,
        metadata_=metadata,
        attachments=[],
    )
    async with AsyncSessionFactory() as session:
        session.add(row)
        await session.commit()

    log.info(
        "autodiscovery_result_inserted",
        source=source,
        url=result.url,
        query=query,
        fetched_iocs=metadata["ioc_count"],
    )
    return True


async def process_query(
    provider: DiscoveryProvider,
    query: str,
    limit: int,
    insert_function: InsertFunction = insert_result,
) -> int:
    results = await asyncio.to_thread(provider.search, query, limit)
    inserted = 0
    for result in results:
        inserted += int(await insert_function(query, result))
    log.info(
        "autodiscovery_query_processed",
        provider=provider.name,
        query=query,
        results=len(results),
        inserted=inserted,
    )
    return inserted


async def run() -> None:
    load_dotenv()
    queries = configured_queries()
    provider = build_provider()
    results_per_query = int(os.getenv("AUTODISCOVERY_RESULTS_PER_QUERY", "10"))
    poll_interval = float(os.getenv("AUTODISCOVERY_POLL_INTERVAL_SECONDS", "3600"))
    query_delay = float(os.getenv("AUTODISCOVERY_QUERY_DELAY_SECONDS", "5"))
    if not 1 <= results_per_query <= 50:
        raise RuntimeError("AUTODISCOVERY_RESULTS_PER_QUERY must be between 1 and 50")
    if poll_interval <= 0 or query_delay < 0:
        raise RuntimeError(
            "Auto-discovery poll interval must be positive and query delay non-negative"
        )

    await init_db()
    log.info(
        "autodiscovery_started",
        provider=provider.name,
        query_count=len(queries),
        results_per_query=results_per_query,
    )
    try:
        while True:
            for index, query in enumerate(queries):
                try:
                    await process_query(provider, query, results_per_query)
                except Exception:
                    log.exception(
                        "autodiscovery_query_failed",
                        provider=provider.name,
                        query=query,
                    )
                if index < len(queries) - 1:
                    await asyncio.sleep(query_delay)
            await asyncio.sleep(poll_interval)
    finally:
        session = getattr(provider, "session", None)
        if session is not None:
            session.close()
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
