"""Transactional current state and immutable source/attempt history on local SQLite."""
import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from access_requests.contracts import ROOT, load_document
from access_requests.extraction import extract
from access_requests.policy import route


def digest(value):
    return hashlib.sha256(value).hexdigest()

class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (document_id TEXT PRIMARY KEY, desired INTEGER, current INTEGER);
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
                source_hash TEXT NOT NULL, source BLOB NOT NULL, filename TEXT NOT NULL,
                settings TEXT NOT NULL, fingerprint TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', pid INTEGER, result TEXT);
            CREATE INDEX IF NOT EXISTS pending_attempts ON attempts(state,fingerprint);
            ''')

    @contextmanager
    def connection(self,write=False):
        db=sqlite3.connect(self.path,timeout=30,isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA busy_timeout=30000')
        try:
            if write:db.execute('BEGIN IMMEDIATE')
            yield db
            if write:db.commit()
        except BaseException:
            if write:db.rollback()
            raise
        finally:db.close()

    def admit(self,document,settings,force=False):
        fingerprint=digest(json.dumps(settings,sort_keys=True).encode())
        with self.connection(True) as db:
            old=db.execute('SELECT a.* FROM documents d JOIN attempts a ON d.desired=a.id WHERE d.document_id=?',(document['document_id'],)).fetchone()
            if old and not force and old['source_hash']==document['source_sha256'] and old['fingerprint']==fingerprint:
                return None
            db.execute('INSERT OR IGNORE INTO documents(document_id) VALUES(?)',(document['document_id'],))
            cursor=db.execute('INSERT INTO attempts(document_id,source_hash,source,filename,settings,fingerprint) VALUES(?,?,?,?,?,?)',
                              (document['document_id'],document['source_sha256'],document['source_bytes'],document['filename'],json.dumps(settings,sort_keys=True),fingerprint))
            attempt=cursor.lastrowid
            db.execute('UPDATE documents SET desired=? WHERE document_id=?',(attempt,document['document_id']))
            return attempt

    def claim(self,fingerprint):
        with self.connection(True) as db:
            row=db.execute("SELECT * FROM attempts WHERE state='pending' AND fingerprint=? ORDER BY id LIMIT 1",(fingerprint,)).fetchone()
            if row is None:return None
            db.execute("UPDATE attempts SET state='running',pid=? WHERE id=?",(os.getpid(),row['id']))
            return dict(row)

    def finish(self,attempt,result):
        with self.connection(True) as db:
            db.execute("UPDATE attempts SET state='completed',result=?,pid=NULL WHERE id=?",(json.dumps(result),attempt['id']))
            db.execute('UPDATE documents SET current=? WHERE document_id=? AND desired=?',(attempt['id'],attempt['document_id'],attempt['id']))

    def current(self):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT a.result FROM documents d JOIN attempts a ON d.current=a.id ORDER BY d.document_id')]

    def history(self,document_id):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT a.result FROM attempts a JOIN documents d USING(document_id) WHERE a.document_id=? AND a.result IS NOT NULL AND a.id!=COALESCE(d.current,0) ORDER BY a.id',(document_id,))]

    def pending(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT id AS attempt_id,document_id,source_hash AS source_sha256,state,pid FROM attempts WHERE state!='completed' ORDER BY id")]

    def recover(self):
        """Requeue claims whose local owning process no longer exists."""
        recovered=0
        with self.connection(True) as db:
            for row in db.execute("SELECT id,pid FROM attempts WHERE state='running'").fetchall():
                try:
                    if row['pid'] is None:raise ProcessLookupError()
                    os.kill(row['pid'],0)
                except ProcessLookupError:
                    db.execute("UPDATE attempts SET state='pending',pid=NULL WHERE id=?",(row['id'],))
                    recovered+=1
                except PermissionError:
                    pass  # A process that exists but is not ours must not be stolen.
        return recovered

    def latest_document(self,document_id):
        with self.connection() as db:
            row=db.execute('SELECT a.* FROM documents d JOIN attempts a ON d.desired=a.id WHERE d.document_id=?',(document_id,)).fetchone()
            if row is None:raise ValueError('Unknown document: '+document_id)
            return {'document_id':document_id,'source_sha256':row['source_hash'],'source_bytes':row['source'],'filename':row['filename'],'message':json.loads(bytes(row['source']).decode())['message']}

class Processor:
    def __init__(self,store,provider,settings=None):
        self.store=store
        self.provider=provider
        self.settings={'provider':getattr(provider,'response_source','mock'),
                       'model':getattr(provider,'model','mock'),
                       'endpoint':getattr(provider,'endpoint',None),
                       'max_output_tokens':getattr(provider,'max_output_tokens',None),
                       'timeout':getattr(provider,'timeout',None),
                       'prompt_sha256':digest((ROOT/'access_requests/prompt.txt').read_bytes()),
                       'schema_sha256':digest((ROOT/'snapshot.schema.json').read_bytes()),
                       'policy_version':digest((ROOT/'materials/office-policy.md').read_bytes())}
        self.settings.update(settings or {})
        self.fingerprint=digest(json.dumps(self.settings,sort_keys=True).encode())

    def process_one(self):
        attempt=self.store.claim(self.fingerprint)
        if attempt is None:return False
        try:
            message=json.loads(bytes(attempt['source']).decode('utf-8'))['message']
            result=extract(self.provider,attempt['document_id'],message)
            if result['extraction'] is not None:
                result.update(route(result['extraction'],message,attempt['document_id']))
            else:result.update(status='error',owner='IT Service Desk',next_action='retry-extraction')
        except Exception as error:
            detail=self.provider.redact(error) if hasattr(self.provider,'redact') else str(error)
            result={'extraction':None,'status':'error','owner':'IT Service Desk','next_action':'retry-extraction',
                    'error':f'{type(error).__name__}: {detail}; retry the affected document',
                    'response_source':getattr(self.provider,'response_source','mock')}
        result.update(document_id=attempt['document_id'],source_sha256=attempt['source_hash'],
                      attempt_id=attempt['id'],input_filename=attempt['filename'],settings=json.loads(attempt['settings']))
        self.store.finish(attempt,result)
        return True

    def run(self,paths=(),force=False,workers=4):
        if workers<1 or workers>32:raise ValueError('workers must be between 1 and 32')
        self.store.recover()
        for path in paths:self.store.admit(load_document(path),self.settings,force=force)
        def drain():
            while self.process_one():pass
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(drain) for _ in range(workers)]
            for future in futures:future.result()
        return self.store.current()

    def retry(self,document_id):
        self.store.admit(self.store.latest_document(document_id),self.settings,force=True)
        return self.run()
