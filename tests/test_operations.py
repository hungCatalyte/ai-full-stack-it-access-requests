import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from support import OfflineCase, ORACLE, FIXTURES, reply

class OperationsCases(OfflineCase):
    def setup_engine(self,script,gates=None):
        from access_requests.repository import Store,Processor
        from access_requests.providers.mock import MockProvider
        store=Store(self.work/'state.sqlite3')
        provider=MockProvider(fixture_dir=FIXTURES,script=script,gates=gates)
        return store,provider,Processor(store,provider)

    def test_t26_overlapping_operators(self):
        from access_requests.repository import Store,Processor
        path=self.export()
        store,p,engine=self.setup_engine({'IT-001.json':[{'reply':'it-001.json'}]})
        engine.run([path]); old=store.current()[0]
        # Simultaneous admission of identical changed bytes across separate processes.
        path=self.export(message=ORACLE['IT-001.json']['message'].replace('2026-11-06','2026-11-07'))
        code="from access_requests.repository import Store,Processor; from access_requests.providers.mock import MockProvider; import sys; Processor(Store(sys.argv[1]),MockProvider(fixture_dir=sys.argv[3],script={'IT-001.json':[{'reply':'it-001-revised.json'}]})).run([sys.argv[2]],workers=2)"
        processes=[subprocess.Popen([sys.executable,'-c',code,str(store.path),str(path),str(FIXTURES)]) for _ in range(2)]
        for process in processes:self.assertEqual(process.wait(timeout=20),0)
        self.assertEqual(len(store.current()),1)
        self.assertEqual(store.current()[0]['extraction']['end_date'],'2026-11-07')
        self.assertEqual(store.history('IT-001.json')[0],old)

    def test_t27_stop_resume(self):
        from access_requests.contracts import load_document
        store,p,engine=self.setup_engine({'IT-001.json':[{'reply':'it-001.json'}],'IT-002.json':[{'reply':'it-002.json'}]})
        a=self.export(); b=self.export('IT-002.json')
        engine.run([a]); old=store.current()[0]
        store.admit(load_document(b),engine.settings)
        code="from access_requests.repository import Store; import sys,os; assert Store(sys.argv[1]).claim(sys.argv[2]); os._exit(0)"
        subprocess.run([sys.executable,'-c',code,str(store.path),engine.fingerprint],check=True,timeout=10)
        self.assertEqual(store.pending()[0]['state'],'running')
        self.assertEqual(store.recover(),1)
        engine.run(workers=2)
        self.assertFalse(store.pending()); self.assertEqual(store.current()[0],old)
        self.assertEqual(len(store.current()),2)

    def test_t28_ready_while_pending(self):
        started,release,done=threading.Event(),threading.Event(),threading.Event()
        store,p,engine=self.setup_engine({'IT-001.json':[{'reply':'it-001.json'}],'IT-002.json':[{'reply':'it-002.json','gate':'slow'}]},gates={'slow':(started,release)})
        original=store.finish
        def finish(attempt,result):
            original(attempt,result)
            if attempt['document_id']=='IT-001.json':done.set()
        store.finish=finish
        paths=[self.export(),self.export('IT-002.json')]
        with ThreadPoolExecutor(max_workers=1) as workers:
            future=workers.submit(engine.run,paths,workers=2)
            try:
                self.assertTrue(started.wait(5)); self.assertTrue(done.wait(5))
                self.assertEqual(store.current()[0]['document_id'],'IT-001.json')
                self.assertEqual(store.pending()[0]['document_id'],'IT-002.json')
                self.assertFalse(future.done())
            finally:release.set()
            future.result(timeout=10)

    def test_t29_service_interruption(self):
        store,p,engine=self.setup_engine({'IT-001.json':[reply('provider-error.json'),{'reply':'it-001.json'}],'IT-002.json':[{'reply':'it-002.json'}]})
        engine.run([self.export(),self.export('IT-002.json')],workers=2)
        self.assertEqual(store.current()[0]['status'],'error')
        other=store.current()[1]
        engine.retry('IT-001.json')
        self.assertEqual(store.current()[1],other)
        self.assertEqual(store.current()[0]['status'],'review')

    def test_t30_atomic_current_publication(self):
        from access_requests.contracts import load_document
        store,p,engine=self.setup_engine({'IT-001.json':[{'reply':'it-001.json'},{'reply':'it-001-revised.json'}]})
        path=self.export(); engine.run([path]); old=store.current()[0]
        path=self.export(message=ORACLE['IT-001.json']['message'].replace('2026-11-06','2026-11-07'))
        store.admit(load_document(path),engine.settings)
        with store.connection() as db:
            db.execute("CREATE TRIGGER crash BEFORE UPDATE OF current ON documents BEGIN SELECT RAISE(ABORT,'injected publication failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):engine.process_one()
        self.assertEqual(store.current()[0],old)
        self.assertEqual(store.history('IT-001.json'),[])

    def test_t31_workload(self):
        from access_requests.repository import Store,Processor
        from access_requests.providers.mock import MockProvider
        # Generated saved replies remain under tests/mock_responses and are cleaned afterward.
        for count in (400,2000):
            with self.subTest(count=count), tempfile.TemporaryDirectory(dir=FIXTURES) as temporary:
                fixtures=__import__('pathlib').Path(temporary)
                paths=[]; script={}
                for i in range(count):
                    name=f'LOAD-{i:04d}.json'
                    message=ORACLE['IT-001.json']['message'].replace('IT-001',name[:-5])
                    path=self.export(name,message); paths.append(path)
                    envelope=reply('it-001.json'); value=copy.deepcopy(ORACLE['IT-001.json']['extraction'])
                    value.update(request_id=name[:-5],supporting_quotes=[message])
                    envelope['output'][0]['content'][0]['text']=json.dumps(value)
                    (fixtures/name).write_text(json.dumps(envelope)); script[name]=[{'reply':name}]
                store=Store(self.work/f'load-{count}.sqlite3')
                Processor(store,MockProvider(fixture_dir=fixtures,script=script)).run(paths,workers=4)
                self.assertEqual(len(store.current()),count); self.assertFalse(store.pending())
                self.assertTrue(all(r['status']=='review' for r in store.current()))
