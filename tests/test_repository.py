from support import OfflineCase, ORACLE, FIXTURES, reply

class RepositoryCases(OfflineCase):
    def engine(self,script,settings=None):
        from access_requests.repository import Store, Processor
        from access_requests.providers.mock import MockProvider
        store=Store(self.work/'state.sqlite3')
        provider=MockProvider(fixture_dir=FIXTURES,script=script)
        return store,provider,Processor(store,provider,settings=settings)
    def test_t21_unchanged_rerun(self):
        path=self.export(); s,p,e=self.engine({'IT-001.json':[{'reply':'it-001.json'}]})
        e.run([path]); e.run([path])
        self.assertEqual(len(p.calls),1); self.assertEqual(len(s.current()),1)
        self.assertEqual(s.current()[0]['extraction'],ORACLE['IT-001.json']['extraction'])
    def test_t22_changed_source(self):
        path=self.export(); s,p,e=self.engine({'IT-001.json':[{'reply':'it-001.json'},{'reply':'it-001-revised.json'}]})
        e.run([path]); original=s.current()[0]
        path=self.export(message=ORACLE['IT-001.json']['message'].replace('2026-11-06','2026-11-07'))
        e.run([path]); current=s.current()[0]
        self.assertEqual(current['extraction']['end_date'],'2026-11-07')
        self.assertNotEqual(current['source_sha256'],original['source_sha256'])
        self.assertEqual(s.history('IT-001.json')[0],original)
    def test_t23_failed_retry_after_success(self):
        path=self.export(); s,p,e=self.engine({'IT-001.json':[{'reply':'it-001.json'},reply('provider-error.json')]})
        e.run([path]); old=s.current()[0]; e.retry('IT-001.json')
        current=s.current()[0]
        self.assertEqual((current['status'],current['owner'],current['next_action']),('error','IT Service Desk','retry-extraction'))
        self.assertIsNone(current['extraction']); self.assertTrue(current['error'])
        self.assertEqual(s.history('IT-001.json')[0],old)
    def test_t24_configuration_refresh(self):
        from access_requests.repository import Processor
        path=self.export(); s,p,e=self.engine({'IT-001.json':[{'reply':'it-001.json'},{'reply':'it-001.json'}]},settings={'model':'A'})
        e.run([path]); old=s.current()[0]
        Processor(s,p,settings={'model':'B'}).run([path])
        self.assertEqual(s.current()[0]['settings']['model'],'B')
        self.assertEqual(s.history('IT-001.json')[0],old)
    def test_t25_incremental_batches(self):
        a=self.export(); b=self.export('IT-002.json')
        s,p,e=self.engine({'IT-001.json':[{'reply':'it-001.json'}],'IT-002.json':[{'reply':'it-002.json'}],'followup.json':[{'reply':'it-001.json'}]})
        e.run([a,b]); e.run([b]); self.assertEqual(len(s.current()),2)
        # A second document about the same business request must not overwrite the first.
        c=self.export('followup.json',ORACLE['IT-001.json']['message'])
        e.run([c]); self.assertEqual(len(s.current()),3)
        self.assertEqual(s.current()[-1]['extraction']['request_id'],'IT-001')
