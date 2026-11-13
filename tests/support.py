"""Independent source expectations and offline fixtures shared by planned cases."""
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'mock_responses'
ORACLE = json.loads((ROOT / 'tests' / 'expected' / 'corpus.json').read_text())

def reply(name):
    return json.loads((FIXTURES / name).read_text())

class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        for name in ('socket', 'create_connection'):
            guard = patch.object(socket, name, side_effect=AssertionError('Tests forbid network access'))
            guard.start()
            self.addCleanup(guard.stop)

    def export(self, name='IT-001.json', message=None):
        path = self.work / name
        path.write_text(json.dumps({'message': message or ORACLE[name]['message']},ensure_ascii=False),encoding='utf-8')
        return path

    def provider(self, names=('IT-001.json',)):
        from access_requests.providers.mock import MockProvider
        return MockProvider(fixture_dir=FIXTURES, script={n:[{'reply':n.lower()}] for n in names})
