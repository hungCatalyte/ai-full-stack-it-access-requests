"""Documented operator interface; real credentials are read only in live mode."""
import argparse
import json
import os
import shlex
from pathlib import Path
from access_requests.contracts import ROOT
from access_requests.repository import Store,Processor


def build_provider(args):
    if args.provider=='mock':
        from access_requests.providers.mock import MockProvider
        directory=Path(args.fixtures)
        script=json.loads(Path(args.script).read_text()) if args.script else {
            p.stem.upper()+'.json':[{'reply':p.name}] for p in directory.glob('*.json')}
        return MockProvider(fixture_dir=directory,script=script)
    from access_requests.providers.openai import OpenAIProvider
    return OpenAIProvider(credential=os.environ.get('API_KEY'),model=args.model or os.environ.get('MODEL_ID','gpt-5-mini'),
                          endpoint=args.endpoint,timeout=args.timeout,max_output_tokens=args.max_output_tokens)


def main(argv=None,provider=None):
    parser=argparse.ArgumentParser(description='Prepare access requests for human review')
    parser.add_argument('--db',default='.state/intake.sqlite3')
    parser.add_argument('--provider',choices=['mock','openai'],default='mock')
    parser.add_argument('--fixtures',default='tests/mock_responses')
    parser.add_argument('--script',help='Saved mock action script')
    parser.add_argument('--model')
    parser.add_argument('--endpoint',default='https://api.openai.com/v1/responses')
    parser.add_argument('--timeout',type=float,default=60)
    parser.add_argument('--max-output-tokens',type=int,default=4096)
    parser.add_argument('--workers',type=int,default=4)
    sub=parser.add_subparsers(dest='command',required=True)
    intake=sub.add_parser('intake'); intake.add_argument('paths',nargs='+'); intake.add_argument('--force',action='store_true')
    sub.add_parser('queue'); sub.add_parser('pending'); sub.add_parser('resume')
    history=sub.add_parser('history'); history.add_argument('document_id')
    retry=sub.add_parser('retry'); retry.add_argument('document_id')
    export=sub.add_parser('export'); export.add_argument('--output',default='deliverables')
    accuracy=sub.add_parser('accuracy'); accuracy.add_argument('--expected',default='tests/expected/corpus.json'); accuracy.add_argument('--output',default='deliverables/accuracy.md')
    args=parser.parse_args(argv)
    if args.command=='accuracy':
        from access_requests.accuracy import write_report
        report=write_report(Store(args.db),args.expected,args.output)
        print(json.dumps(report)); return 0
    store=Store(args.db)
    try:
        if args.command in ('intake','retry','resume'):
            processor=Processor(store,provider or build_provider(args))
            if args.command=='intake':
                paths=[]
                for item in args.paths:
                    path=Path(item)
                    paths.extend(sorted(path.glob('*.json')) if path.is_dir() else [path])
                result=processor.run(paths,force=args.force,workers=args.workers)
            elif args.command=='retry':result=processor.retry(args.document_id)
            else:result=processor.run(workers=args.workers)
        elif args.command=='queue':
            result=store.current()
            for record in result:
                if record['status']=='error':
                    command=['python3','-m','access_requests','--db',args.db,'--provider',args.provider,'--fixtures',args.fixtures]
                    if args.script:command.extend(['--script',args.script])
                    if args.model:command.extend(['--model',args.model])
                    command.extend(['--endpoint',args.endpoint,'--timeout',str(args.timeout),'--max-output-tokens',str(args.max_output_tokens),'retry',record['document_id']])
                    record['retry_command']=shlex.join(command)
        elif args.command=='pending':result=store.pending()
        elif args.command=='history':result=store.history(args.document_id)
        else:
            from access_requests.snapshots import export_current
            result={'generation':export_current(store,args.output),'output':args.output}
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return int(isinstance(result,list) and any(r.get('status')=='error' for r in result))
    except (ValueError,OSError) as error:
        print(json.dumps({'error':str(error)})); return 2
