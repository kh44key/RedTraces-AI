"""Dependency-light configuration tests for the Discord collector."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from collectors.discord_collector import configured_channel_ids


class DiscordConfigurationTest(unittest.TestCase):
    def test_parses_and_deduplicates_channel_ids(self) -> None:
        with patch.dict(
            os.environ,
            {"DISCORD_CHANNEL_IDS": "123, 456,123"},
            clear=False,
        ):
            self.assertEqual(configured_channel_ids(), {123, 456})

    def test_rejects_missing_channel_ids(self) -> None:
        with patch.dict(os.environ, {"DISCORD_CHANNEL_IDS": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "at least one"):
                configured_channel_ids()

    def test_rejects_non_numeric_channel_ids(self) -> None:
        with patch.dict(
            os.environ,
            {"DISCORD_CHANNEL_IDS": "123,not-a-channel"},
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "numeric"):
                configured_channel_ids()


if __name__ == "__main__":
    unittest.main()
