"""Source-derived expected facts remain independent of measured extraction records."""
import json
from pathlib import Path

FIELDS=('request_id','request_date','kind','requester','team','system','environment','permission','business_purpose','start_date','end_date','manager')
ROUTES={'B1':('review','IT Service Desk','inspect-message'),'B2':('review','IT Service Desk','confirm-withdrawal'),'B3':('needs-information','IT Service Desk','clarify'),'B4':('review','Security Review','review-risk-then-owner'),'B5':('review','System Owner','review-request')}

def compare(records,expected):
    current={record['document_id']:record for record in records}
    report={'matched':0,'denominator':15*len(expected),'factual_errors':[],
            'comparison_mismatches':[],'supporting_quote_errors':[],'extraction_errors':[],
            'extra_documents':sorted(set(current)-set(expected)),'response_sources':sorted({r['response_source'] for r in records})}
    for name,profile in expected.items():
        record=current.get(name)
        if not record or not record.get('extraction') or record.get('error'):
            report['extraction_errors'].append({'document_id':name,'error':record.get('error') if record else 'missing record'})
            continue
        wanted=dict(profile['extraction'])
        wanted.update(zip(('status','owner','next_action'),ROUTES[profile['rule']]))
        actual=dict(record['extraction']); actual.update({k:record[k] for k in ('status','owner','next_action')})
        for field in FIELDS+('status','owner','next_action'):
            if actual.get(field)==wanted[field]:report['matched']+=1
            else:
                error={'document_id':name,'field':field,'expected':wanted[field],'actual':actual.get(field)}
                report['comparison_mismatches'].append(error)
                # Purpose paraphrases require human factual adjudication; exact mismatch is not automatically hallucination.
                if field!='business_purpose':report['factual_errors'].append(error)
        for quote in record['extraction']['supporting_quotes']:
            if quote not in profile['message']:report['supporting_quote_errors'].append({'document_id':name,'quote':quote})
    return report


def write_report(store,expected_path,output):
    expected=json.loads(Path(expected_path).read_text())
    records=store.current()
    report=compare(records,expected)
    config=[{'document_id':r['document_id'],'response_source':r['response_source'],'settings':r['settings']} for r in records]
    lines=['# Accuracy check','',
           'Observation: saved mock replies, not live model accuracy. No live observations were performed. No API key or real model was used for this report.',
           '', '## Procedure and counting', '',
           'Expected facts below were authored from the original messages and office policy before application implementation, in tests/expected/accuracy.json; they are not inferred from the outputs being compared. The separate saved response fixtures are deterministic development examples.',
           '', 'Compare the twelve scalar extraction fields and status/owner/next_action by exact equality: 15 cells per message. Null matches null, but a missing record or an extraction error counts all 15 cells as unmatched. No case, whitespace, name, or date normalization is applied during scoring. Each expected document counts once; unexpected documents are listed separately, outside the denominator. There is no passing-score threshold in the brief.',
           '', 'With 20 supplied messages and one authored paraphrase, the denominator is 315. supporting_quotes and issues are checked separately by schema, substring, and policy tests; they are not counted as scalar accuracy cells. Date corrections and conflicting alternatives use the source-derived expectations. Purpose uses a preselected exact source excerpt: a paraphrase mismatch needs human factual adjudication and is not automatically a factual error.',
           '', 'Factual-error reporting: non-purpose scalar/routing mismatches are listed individually with document, field, expected and actual values; extraction errors and unsupported quotes have separate lists. Review differences against the quoted message and office policy. This mock score establishes the comparison procedure, not the ability of the configured live model to extract fresh text.',
           '', '## Recorded mock comparison', '',
           f"Matched: **{report['matched']}/{report['denominator']}**. Factual mismatches: **{len(report['factual_errors'])}**. Extraction errors: **{len(report['extraction_errors'])}**.",
           '', 'Reproduce after mock intake: `env -u API_KEY python3 -m access_requests --db .state/submission.sqlite3 accuracy --expected tests/expected/accuracy.json --output deliverables/accuracy.md`.',
           '', '## Expected facts and source evidence', '',
           'All extracted fields, including nulls, supporting_quotes, and explanatory issues, are recorded below. The routing triples come from materials/office-policy.md rules 1–5, in order. Each document identity is its input filename; internal request_id is extracted from message text.',
           '', '| Document | Source-derived expected extraction | Expected routing (status / owner / next_action) | Exact source message |',
           '| --- | --- | --- | --- |']
    for name,profile in expected.items():
        facts=json.dumps(profile['extraction'],ensure_ascii=False)
        quotes=' '.join('“'+part+'”' for part in profile['message'].split('\n') if part.strip())
        lines.append('| '+name+' | '+facts+' | '+' / '.join(ROUTES[profile['rule']])+' | '+quotes+' |')
    from access_requests.contracts import ROOT
    policy=(ROOT/'materials/office-policy.md').read_text()
    lines+=['','Policy source for the expected routing:','']
    lines+=['> '+line for line in policy.splitlines() if line[:2] in ('1.','2.','3.','4.','5.')]
    lines+=['','## Comparison details','','```json',json.dumps(report,indent=2),'```',
            '', '## Recorded configuration and response sources', '',
            'Mock response_source is mock. Live adapter support is OpenAI Responses with configurable model, default gpt-5-mini, JSON Schema strict output, low reasoning effort, maximum 4096 output tokens, 60-second request timeout, and no automatic retry. The live model has not been called in these observations.',
            '', '```json',json.dumps(config,indent=2),'```','']
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text('\n'.join(lines))
    return report
