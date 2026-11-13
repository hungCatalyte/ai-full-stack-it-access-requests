"""T01: the file-backed, isolated mock provider contract from planning/plan.md."""

import importlib
import json
import shutil
import socket
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


FIXTURES = Path(__file__).resolve().parent / "mock_responses"


class MockProviderContract(unittest.TestCase):
    def test_t01_mock_provider_contract(self):
        """Saved replies, failures, retries, and gates work without a key or network."""
        no_network = mock.Mock(side_effect=AssertionError("T01 opened a network connection"))
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(socket, "socket", no_network),
            mock.patch.object(socket, "create_connection", no_network),
        ):
            fixture_dir = Path(temporary)
            for name in ("harness-success.json", "harness-cutoff.json", "harness-script.json"):
                shutil.copyfile(FIXTURES / name, fixture_dir / name)
            success = json.loads((fixture_dir / "harness-success.json").read_text())
            cutoff = json.loads((fixture_dir / "harness-cutoff.json").read_text())
            script = json.loads((fixture_dir / "harness-script.json").read_text())

            # This interface is deliberately absent in the test-first commit.
            module = importlib.import_module("access_requests.providers.mock")
            started, release = threading.Event(), threading.Event()
            provider = module.MockProvider(
                fixture_dir=fixture_dir,
                script=script,
                gates={"slow": (started, release)},
            )
            message = "T01 lookup input; no business extraction is being tested."

            with self.subTest("saved success and ordered retry responses"):
                self.assertEqual(provider.extract("IT-001.json", message), success)
                with self.assertRaisesRegex(module.MockProviderError, "temporary provider outage"):
                    provider.extract("IT-001.json", message)
                self.assertEqual(provider.extract("IT-001.json", message), cutoff)
                self.assertEqual(success["response_source"], "mock")
                self.assertEqual(cutoff["status"], "incomplete")

            with self.subTest("pause is explicit and does not block another document"):
                with ThreadPoolExecutor(max_workers=2) as workers:
                    slow = workers.submit(provider.extract, "IT-002.json", message)
                    try:
                        self.assertTrue(started.wait(timeout=2), "mock never reached its gate")
                        self.assertFalse(slow.done(), "gated reply returned before release")
                        other = workers.submit(provider.extract, "IT-003.json", message)
                        self.assertEqual(other.result(timeout=2), success)
                        self.assertFalse(slow.done(), "another call released the gated reply")
                    finally:
                        release.set()
                    self.assertEqual(slow.result(timeout=2), success)

            with self.subTest("trace includes successes, failed attempts, and pending calls"):
                self.assertEqual(
                    provider.calls,
                    [
                        {"document_id": document_id, "message": message}
                        for document_id in (
                            "IT-001.json", "IT-001.json", "IT-001.json",
                            "IT-002.json", "IT-003.json",
                        )
                    ],
                )
            no_network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
