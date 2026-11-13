import json
from support import OfflineCase, ORACLE, FIXTURES, reply

class ExtractionCases(OfflineCase):
    def service(self, fixture):
        from access_requests.extraction import extract
        from access_requests.providers.mock import MockProvider
        provider=MockProvider(fixture_dir=FIXTURES,script={'IT-001.json':[{'reply':fixture}]})
        return extract(provider,'IT-001.json',ORACLE['IT-001.json']['message'])

    def test_t04_extraction_facts(self):
        from access_requests.extraction import extract
        for name,profile in ORACLE.items():
            with self.subTest(name=name):
                result=extract(self.provider((name,)),name,profile['message'])
                self.assertIsNone(result['error'])
                self.assertEqual(result['extraction'],profile['extraction'])
                self.assertEqual(result['response_source'],'mock')

    def test_t05_malformed_output(self):
        for name in ('malformed-json.json','schema-invalid-envelope.json'):
            result=self.service(name)
            self.assertIsNone(result['extraction']); self.assertTrue(result['error'])

    def test_t06_refusal(self):
        result=self.service('refusal.json')
        self.assertIsNone(result['extraction']); self.assertIn('refusal',result['error'])

    def test_t07_interrupted_response(self):
        result=self.service('incomplete.json')
        self.assertIsNone(result['extraction']); self.assertIn('incomplete',result['error'])

    def test_t08_provider_failure(self):
        from access_requests.extraction import extract
        from access_requests.providers.mock import MockProvider
        provider=MockProvider(fixture_dir=FIXTURES,script={'IT-001.json':[reply('provider-error.json')], 'IT-002.json':[{'reply':'it-002.json'}]})
        failed=extract(provider,'IT-001.json',ORACLE['IT-001.json']['message'])
        self.assertIsNone(failed['extraction']); self.assertTrue(failed['error'])
        self.assertEqual(extract(provider,'IT-002.json',ORACLE['IT-002.json']['message'])['extraction'],ORACLE['IT-002.json']['extraction'])

    def test_t09_provider_request_and_redaction(self):
        from access_requests.providers.openai import OpenAIProvider
        from access_requests.extraction import extract
        calls=[]
        def transport(url,headers,payload,timeout):
            calls.append((url,headers,payload,timeout)); return reply('it-001.json')
        provider=OpenAIProvider(credential='offline-sentinel',model='configured-model',transport=transport)
        result=extract(provider,'IT-001.json',ORACLE['IT-001.json']['message'])
        self.assertEqual(result['response_source'],'openai:mock')
        self.assertEqual(calls[0][1]['Authorization'],'Bearer offline-sentinel')
        self.assertEqual(calls[0][2]['model'],'configured-model')
        self.assertEqual(calls[0][2]['input'][0]['content'],ORACLE['IT-001.json']['message'])
        self.assertNotIn('offline-sentinel',json.dumps(provider.evidence(ORACLE['IT-001.json']['message'])))
        def failing(*args):raise RuntimeError('offline-sentinel should be redacted')
        provider.transport=failing
        result=extract(provider,'IT-001.json',ORACLE['IT-001.json']['message'])
        self.assertNotIn('offline-sentinel',result['error'])
