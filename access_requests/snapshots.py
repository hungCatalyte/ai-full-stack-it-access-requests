"""Publish immutable generations; readers pin one manifest for coherent joins."""
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path


def _write(path,text):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary=tempfile.mkstemp(dir=path.parent,prefix='.publish-')
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

def export_current(store,output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    with (output/'.export.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        records=store.current()
        generation=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
        rows=[dict(record,generation=generation) for record in records]
        queue=[{key:record[key] for key in ('document_id','source_sha256','attempt_id','status','owner','next_action','generation')} for record in rows]
        extraction_text=''.join(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n' for row in rows)
        queue_text=json.dumps({'generation':generation,'requests':queue},indent=2,ensure_ascii=False)+'\n'
        directory=output/'.snapshots'/generation
        _write(directory/'extractions.jsonl',extraction_text)
        _write(directory/'queue.json',queue_text)
        # Root files are convenience exports. Concurrent readers use the pinned manifest.
        _write(output/'extractions.jsonl',extraction_text)
        _write(output/'queue.json',queue_text)
        _write(output/'current.json',json.dumps({'generation':generation},indent=2)+'\n')
        return generation

def read_export(output):
    output=Path(output)
    generation=json.loads((output/'current.json').read_text())['generation']
    if len(generation)!=64 or any(c not in '0123456789abcdef' for c in generation):
        raise ValueError('Invalid snapshot generation')
    directory=output/'.snapshots'/generation
    rows=[json.loads(line) for line in (directory/'extractions.jsonl').read_text().splitlines()]
    queue=json.loads((directory/'queue.json').read_text())
    if queue['generation']!=generation or any(row['generation']!=generation for row in rows):
        raise ValueError('Snapshot generation mismatch')
    if {(r['document_id'],r['source_sha256'],r['attempt_id']) for r in rows}!={(r['document_id'],r['source_sha256'],r['attempt_id']) for r in queue['requests']}:
        raise ValueError('Queue/extraction source mismatch')
    return {'generation':generation,'extractions':rows,'queue':queue['requests']}
