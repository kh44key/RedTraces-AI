"""Tests for the dark-web collector's fetch, parse, and insert pipeline."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from collectors.darkweb_collector import DarkWebAdapter, process_target


class MockAdapter(DarkWebAdapter):
    def parse(self, html: str) -> list[dict]:
        if html != "<html>mock forum</html>":
            return []
        return [
            {
                "body": "Example post body",
                "author": "researcher",
                "url": "/thread/42#post-7",
                "posted_at": "2026-07-28T12:00:00Z",
                "forum_name": "Mock Forum",
                "thread_title": "Example thread",
            }
        ]


class ProcessTargetTest(unittest.IsolatedAsyncioTestCase):
    async def test_mocked_response_is_parsed_and_inserted(self) -> None:
        response = Mock()
        response.text = "<html>mock forum</html>"
        response.raise_for_status.return_value = None
        http_session = Mock()
        http_session.get.return_value = response
        insert = AsyncMock(return_value=True)

        with patch.dict(
            "os.environ",
            {
                "DARKWEB_RETRY_ATTEMPTS": "1",
                "DARKWEB_REQUEST_TIMEOUT_SECONDS": "5",
            },
        ):
            inserted = await process_target(
                http_session,
                "http://examplemockaddress.onion/forum/",
                MockAdapter(),
                insert,
            )

        self.assertEqual(inserted, 1)
        http_session.get.assert_called_once_with(
            "http://examplemockaddress.onion/forum/", timeout=5.0
        )
        insert.assert_awaited_once()
        source, target, post = insert.await_args.args
        self.assertEqual(source, "examplemockaddress.onion")
        self.assertEqual(target, "http://examplemockaddress.onion/forum/")
        self.assertEqual(post["body"], "Example post body")
        self.assertEqual(post["thread_title"], "Example thread")


if __name__ == "__main__":
    unittest.main()
