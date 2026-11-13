import hashlib
import json
from support import OfflineCase,ORACLE,ROOT

class HandoverCases(OfflineCase):
    def test_t37_documented_handover(self):
        from access_requests.cli import main
        from contextlib import redirect_stdout
        import io
        readme=(ROOT/'README.md').read_text()
        for term in ('Python 3.11','OpenAI','API_KEY','MODEL_ID','intake','queue','accuracy','retry','resume','unittest discover','mock'):
            self.assertIn(term,readme)
        self.assertTrue((ROOT/'requirements.lock').exists())
        self.assertTrue((ROOT/'access_requests/prompt.txt').exists())
        output=io.StringIO()
        with redirect_stdout(output):
            code=main(['--db',str(self.work/'state.sqlite3'),'intake',str(self.export())],provider=self.provider())
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())[0]['next_action'],'review-request')

    def test_t38_submission_artifacts(self):
        from access_requests.contracts import validate_extraction
        directory=ROOT/'deliverables'
        names=('extractions.jsonl','queue.json','accuracy.md','request-evidence.json','verification.md')
        for name in names:self.assertTrue((directory/name).is_file(),name)
        rows=[json.loads(line) for line in (directory/'extractions.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),21)
        self.assertEqual(len({r['document_id'] for r in rows}),21)
        queue=json.loads((directory/'queue.json').read_text())['requests']
        self.assertEqual({r['document_id'] for r in rows},{q['document_id'] for q in queue})
        for row in rows:
            self.assertEqual(row['response_source'],'mock')
            self.assertIsNone(row['error'])
            validate_extraction(row['extraction'],ORACLE[row['document_id']]['message'])
            source=ROOT/('materials/paraphrase' if row['document_id']=='IT-P01.json' else 'materials/requests')/row['document_id']
            self.assertEqual(row['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            linked=next(q for q in queue if q['document_id']==row['document_id'])
            for field in ('source_sha256','attempt_id','status','owner','next_action'):self.assertEqual(row[field],linked[field])
        evidence=json.loads((directory/'request-evidence.json').read_text())
        self.assertEqual(evidence['request']['model'],'gpt-5-mini')
        self.assertEqual(evidence['headers']['Authorization'],'Bearer [REDACTED]')
        self.assertIn('response_handling',evidence)
        self.assertEqual(evidence['observation']['response_source'],'mock')
        self.assertIn('315/315',(directory/'accuracy.md').read_text())
        verification=(directory/'verification.md').read_text()
        for term in ('mock','Operating limits','Observed results','unittest discover','assert'):
            self.assertIn(term,verification)
