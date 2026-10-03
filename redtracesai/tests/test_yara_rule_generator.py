"""Tests for compile-validated hash IOC YARA generation."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

try:
    import yara
except ModuleNotFoundError:
    yara = None

from common.stix_generator import build_stix_bundle
from common.stix_store import STIXStore
from common.yara_rule_generator import (
    HashIOC,
    build_rule_block,
    compile_rule_blocks,
    generate_yara_rules,
)


class YARARuleGeneratorTest(unittest.TestCase):
    def test_renders_extension_friendly_hash_rule_block(self) -> None:
        block = build_rule_block(
            HashIOC(value="a" * 32, hash_type="md5", source='channel "one"'),
            1,
            date(2026, 8, 2),
        )
        self.assertIn("rule Auto_Generated_0001", block)
        self.assertIn('source = "channel \\"one\\""', block)
        self.assertIn('date = "2026-08-02"', block)
        self.assertIn('hash_type = "md5"', block)
        self.assertIn('hash.md5(0, filesize) == "' + "a" * 32 + '"', block)

    @unittest.skipUnless(yara is not None, "yara-python is unavailable on this host ABI")
    def test_generates_one_compiled_rule_per_hash(self) -> None:
        records = [
            {
                "ioc_type": "md5",
                "value": "a" * 32,
                "platform": "telegram",
                "source": "malware-channel",
            },
            {
                "ioc_type": "sha1",
                "value": "b" * 40,
                "platform": "darkweb",
                "source": "forum.onion",
            },
            {
                "ioc_type": "sha256",
                "value": "c" * 64,
                "platform": "reddit",
                "source": "netsec",
            },
            {
                "ioc_type": "domain",
                "value": "ignored.example",
                "platform": "telegram",
                "source": "channel",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with STIXStore(root / "store.sqlite3") as store:
                store.ingest_bundle(build_stix_bundle(records))
            result = generate_yara_rules(
                database_path=root / "store.sqlite3",
                output_directory=root / "rules",
                generated_on=date(2026, 8, 2),
            )
            source = result.path.read_text(encoding="utf-8")
            yara.compile(source=source)

            self.assertEqual(result.path.name, "2026-08-02.yar")
            self.assertEqual(result.generated_rules, 3)
            self.assertEqual(result.discarded_rules, 0)
            self.assertEqual(source.count("rule Auto_Generated_"), 3)
            self.assertIn('hash.md5(0, filesize) == "' + "a" * 32 + '"', source)
            self.assertIn('hash.sha1(0, filesize) == "' + "b" * 40 + '"', source)
            self.assertIn('hash.sha256(0, filesize) == "' + "c" * 64 + '"', source)
            self.assertIn("v1 limitation", source)
            self.assertNotIn("ignored.example", source)

    @unittest.skipUnless(yara is not None, "yara-python is unavailable on this host ABI")
    def test_discards_only_the_block_that_fails_compilation(self) -> None:
        blocks = ["rule Auto_Generated_0001 { condition: true }", "invalid rule"]
        real_compile = yara.compile

        def compile_side_effect(*, source: str):
            if "invalid rule" in source:
                raise yara.SyntaxError("invalid test rule")
            return real_compile(source=source)

        with patch("common.yara_rule_generator.yara.compile", side_effect=compile_side_effect):
            valid, discarded = compile_rule_blocks(blocks)
        self.assertEqual(valid, [blocks[0]])
        self.assertEqual(discarded, 1)

    @unittest.skipUnless(yara is not None, "yara-python is unavailable on this host ABI")
    def test_fails_when_store_has_no_hash_iocs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with STIXStore(root / "store.sqlite3") as store:
                store.ingest_bundle(
                    build_stix_bundle(
                        [
                            {
                                "ioc_type": "ipv4",
                                "value": "1.2.3.4",
                                "platform": "telegram",
                                "source": "channel",
                            }
                        ]
                    )
                )
            with self.assertRaises(ValueError):
                generate_yara_rules(
                    database_path=root / "store.sqlite3",
                    output_directory=root / "rules",
                )


if __name__ == "__main__":
    unittest.main()
