import contextlib
import io
import json
from support import OfflineCase, ORACLE, FIXTURES, reply

class CliCases(OfflineCase):
    def invoke(self,args,provider=None):
        from access_requests.cli import main
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=main(['--db',str(self.work/'state.sqlite3'),*args],provider=provider)
        return code,json.loads(output.getvalue())

    def test_t32_operator_commands(self):
        from access_requests.providers.mock import MockProvider
        provider=MockProvider(fixture_dir=FIXTURES,script={'IT-001.json':[reply('provider-error.json'),{'reply':'it-001.json'}]})
        path=self.export()
        code,records=self.invoke(['intake',str(path)],provider)
        self.assertEqual(code,1); self.assertEqual(records[0]['status'],'error')
        code,records=self.invoke(['queue'])
        self.assertEqual(records[0]['owner'],'IT Service Desk')
        self.assertIn('retry IT-001.json',records[0]['retry_command'])
        code,records=self.invoke(['retry','IT-001.json'],provider)
        self.assertEqual(code,0); self.assertEqual(records[0]['status'],'review')
        self.assertEqual(self.invoke(['pending'])[1],[])
        self.assertEqual(len(self.invoke(['history','IT-001.json'])[1]),1)
        self.assertEqual(self.invoke(['resume'],provider)[0],0)

    def test_t33_coherent_exports(self):
        from access_requests.repository import Store,Processor
        from access_requests.snapshots import export_current,read_export
        store=Store(self.work/'state.sqlite3')
        Processor(store,self.provider()).run([self.export()])
        out=self.work/'deliverables'
        export_current(store,out)
        snapshot=read_export(out)
        rows=snapshot['extractions']; queue=snapshot['queue']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['extraction'],ORACLE['IT-001.json']['extraction'])
        self.assertEqual(rows[0]['document_id'],queue[0]['document_id'])
        self.assertEqual(rows[0]['source_sha256'],queue[0]['source_sha256'])
        self.assertEqual(rows[0]['attempt_id'],queue[0]['attempt_id'])
        self.assertIsNone(rows[0]['error']); self.assertEqual(rows[0]['response_source'],'mock')
        self.assertEqual(json.loads((out/'queue.json').read_text())['requests'],queue)
        self.assertTrue((out/'extractions.jsonl').read_text().endswith('\n'))
        # A failed manifest publication must leave the previous immutable snapshot readable.
        from unittest.mock import patch
        import os
        real_replace=os.replace
        def interrupt(source,target):
            if str(target).endswith('current.json'):raise OSError('injected export interruption')
            return real_replace(source,target)
        with patch('access_requests.snapshots.os.replace',side_effect=interrupt):
            with self.assertRaises(OSError):export_current(store,out)
        self.assertEqual(read_export(out),snapshot)
