import copy
import hashlib
import json
from support import OfflineCase, ORACLE, ROOT

class InputContracts(OfflineCase):
    def test_t02_input_identity_hash_and_boundary(self):
        from access_requests.contracts import load_document
        for path in sorted((ROOT/'materials/requests').glob('*.json')):
            record=load_document(path)
            self.assertEqual(record['document_id'],path.name)
            self.assertEqual(record['source_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record['message'],ORACLE[path.name]['message'])
        path=self.export('IT-B200.json')
        self.assertEqual(len(load_document(path)['message'].split()),200)
        old=load_document(path)
        path.write_bytes(path.read_bytes()+b'\n')
        self.assertNotEqual(old['source_sha256'],load_document(path)['source_sha256'])
        self.assertEqual(old['message'],load_document(path)['message'])

    def test_t03_schema_and_exact_quote_validation(self):
        from access_requests.contracts import validate_extraction
        baseline=ORACLE['IT-001.json']['extraction']
        message=ORACLE['IT-001.json']['message']
        self.assertEqual(validate_extraction(baseline,message),baseline)
        mutations=[]
        for key in baseline:
            bad=copy.deepcopy(baseline); del bad[key]; mutations.append(bad)
        for key in list(baseline)[:12]:
            for wrong in (1,True,[],{}):
                bad=copy.deepcopy(baseline); bad[key]=wrong; mutations.append(bad)
        for key in ('kind','environment','permission'):
            bad=copy.deepcopy(baseline); bad[key]='invalid'; mutations.append(bad)
        for key in ('issues','supporting_quotes'):
            for wrong in ('text',[1]):
                bad=copy.deepcopy(baseline); bad[key]=wrong; mutations.append(bad)
        bad=copy.deepcopy(baseline); bad['extra']='x'; mutations.append(bad)
        bad=copy.deepcopy(baseline); bad['supporting_quotes']=['Invented supporting quotation']; mutations.append(bad)
        for bad in mutations:
            with self.subTest(bad=bad), self.assertRaises(ValueError):validate_extraction(bad,message)
