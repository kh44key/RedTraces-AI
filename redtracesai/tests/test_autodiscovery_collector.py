"""Tests for the provider-driven auto-discovery flow."""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from collectors.autodiscovery_collector import (
    DiscoveryProvider,
    DiscoveryResult,
    GoogleCSEProvider,
    configured_queries,
    process_query,
)


class MockProvider(DiscoveryProvider):
    name = "mock"

    def search(self, query: str, limit: int) -> list[DiscoveryResult]:
        return [
            DiscoveryResult(
                title="Synthetic malware report",
                snippet="Report includes C2 at node[.]example",
                url="https://research.example/report",
                display_link="research.example",
                rank=1,
            )
        ][:limit]


class AutoDiscoveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_to_insert_flow(self) -> None:
        insert = AsyncMock(return_value=True)
        inserted = await process_query(MockProvider(), "malware IOC", 10, insert)

        self.assertEqual(inserted, 1)
        insert.assert_awaited_once()
        query, result = insert.await_args.args
        self.assertEqual(query, "malware IOC")
        self.assertEqual(result.display_link, "research.example")

    def test_google_provider_normalizes_public_http_results(self) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "items": [
                {
                    "title": "Threat report",
                    "snippet": "Malware indicators",
                    "link": "https://research.example/report",
                    "displayLink": "research.example",
                },
                {
                    "title": "Ignored",
                    "snippet": "Unsupported scheme",
                    "link": "ftp://files.example/report",
                },
            ]
        }
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        with patch.dict(
            os.environ,
            {
                "AUTODISCOVERY_RETRY_ATTEMPTS": "1",
                "AUTODISCOVERY_REQUEST_TIMEOUT_SECONDS": "5",
            },
            clear=False,
        ):
            provider = GoogleCSEProvider("key", "cx", session)
            results = provider.search("malware IOC", 10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://research.example/report")
        session.get.assert_called_once()

    def test_queries_are_double_pipe_separated_and_deduplicated(self) -> None:
        with patch.dict(
            os.environ,
            {"AUTODISCOVERY_QUERIES": "malware IOC||ransomware report||malware IOC"},
            clear=False,
        ):
            self.assertEqual(
                configured_queries(), ["malware IOC", "ransomware report"]
            )


if __name__ == "__main__":
    unittest.main()
