import json
from support import OfflineCase,ORACLE,ROOT,reply

class AccuracyCases(OfflineCase):
    def test_t34_paraphrase(self):
        from access_requests.repository import Store,Processor
        from access_requests.accuracy import compare
        name='IT-P01.json'; path=self.export(name)
        store=Store(self.work/'state.sqlite3')
        Processor(store,self.provider((name,))).run([path])
        self.assertEqual(store.current()[0]['extraction']['request_id'],'IT-P01')
        self.assertEqual(store.current()[0]['owner'],'System Owner')
        report=compare(store.current(),{name:ORACLE[name]})
        self.assertEqual((report['matched'],report['denominator']),(15,15))

    def test_t35_full_corpus_independent_expectations(self):
        from access_requests.repository import Store,Processor
        from access_requests.accuracy import write_report
        expected=json.loads((ROOT/'tests/expected/accuracy.json').read_text())
        store=Store(self.work/'state.sqlite3')
        Processor(store,self.provider(tuple(expected))).run([self.export(n) for n in expected])
        path=self.work/'accuracy.md'
        report=write_report(store,ROOT/'tests/expected/accuracy.json',path)
        self.assertEqual((report['matched'],report['denominator']),(315,315))
        self.assertFalse(report['factual_errors'])
        text=path.read_text()
        self.assertIn('mock',text); self.assertIn('not live',text)
        for name,profile in expected.items():
            self.assertIn(name,text); self.assertIn(profile['extraction']['business_purpose'],text)
            self.assertTrue(all(q in profile['message'] for q in profile['extraction']['supporting_quotes']))

    def test_t36_counting_and_factual_errors(self):
        from access_requests.accuracy import compare
        expected={'IT-001.json':ORACLE['IT-001.json']}
        self.assertEqual(compare([reply('accuracy-correct.json')],expected)['matched'],15)
        for name in ('accuracy-wrong-field.json','accuracy-null-mismatch.json'):
            report=compare([reply(name)],expected)
            self.assertEqual((report['matched'],report['denominator']),(14,15))
            self.assertEqual(len(report['factual_errors']),1)
        self.assertEqual(compare([reply('accuracy-error.json')],expected)['matched'],0)
        self.assertEqual(compare([],expected)['denominator'],15)
        self.assertEqual(compare([],expected)['matched'],0)
