"""File-backed provider for deterministic, credential-free development examples."""

import json
from collections import deque
from pathlib import Path
from threading import Lock


class MockProviderError(RuntimeError):
    """A scripted failure or a missing mock response."""


class MockProvider:
    """Consume each document's script independently and record attempted calls.

    Replies and error messages come from saved fixtures. Optional gates contain
    (started, release) events so tests can control delays without sleeping.
    """

    def __init__(self, *, fixture_dir, script, gates=None):
        self.fixture_dir = Path(fixture_dir)
        self._scripts = {document: deque(actions) for document, actions in script.items()}
        self._gates = dict(gates or {})
        self._lock = Lock()
        self.calls = []

    def extract(self, document_id, message):
        with self._lock:
            self.calls.append({"document_id": document_id, "message": message})
            actions = self._scripts.get(document_id)
            if not actions:
                raise MockProviderError(f"No scripted response remains for {document_id}")
            action = actions.popleft()

        # Waiting or reading a fixture must not hold up another document's call.
        if "gate" in action:
            try:
                started, release = self._gates[action["gate"]]
            except KeyError as error:
                raise MockProviderError(f"Unknown mock gate: {action['gate']}") from error
            started.set()
            release.wait()

        if "error" in action:
            raise MockProviderError(action["error"])

        try:
            return json.loads(
                (self.fixture_dir / action["reply"]).read_text(encoding="utf-8")
            )
        except (KeyError, OSError, ValueError) as error:
            raise MockProviderError(f"Cannot load mock response for {document_id}: {error}") from error
