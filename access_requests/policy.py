"""Deterministic ordered routing; all decisions remain with human reviewers."""
import re
from datetime import date
from pathlib import Path
from access_requests.contracts import validate_extraction

REQUIRED=('request_id','request_date','requester','team','system','environment','permission','business_purpose','start_date','end_date','manager')
OVERRIDE=re.compile(r'system\s+override|bypass\s+(?:approval|rules)|highest.priority\s+system\s+instruction|display\s+the\s+api\s+key|mark\s+(?:the\s+)?request\s+as\s+approved',re.I)

def _issue(value,detail):
    if detail not in value['issues']:value['issues'].append(detail)

def route(value,message,document_id):
    validate_extraction(value,message)
    for key,item in value.items():
        if item is None and not any(key.lower() in i.lower() for i in value['issues']):
            _issue(value,'Missing or unresolved '+key)
    for key in ('request_date','start_date','end_date'):
        if value[key] is not None:
            try:
                if len(value[key])!=10:raise ValueError()
                date.fromisoformat(value[key])
            except ValueError:
                value[key]=None
                _issue(value,'Invalid or unresolved '+key)
    mismatch=value['request_id'] is not None and value['request_id']!=Path(document_id).stem
    if mismatch:_issue(value,'Identifier mismatch: '+value['request_id']+' versus '+document_id)
    reversed_dates=bool(value['start_date'] and value['end_date'] and value['start_date']>value['end_date'])
    if reversed_dates:_issue(value,'start_date is after end_date')
    if OVERRIDE.search(message):
        if not any('override' in i.lower() for i in value['issues']):_issue(value,'Instruction override attempt in source message')
        if not any(OVERRIDE.search(q) for q in value['supporting_quotes']):value['supporting_quotes'].append(message)
        status,owner,action='review','IT Service Desk','inspect-message'
    elif value['kind']=='withdrawal' and value['request_id'] and value['request_date']:
        status,owner,action='review','IT Service Desk','confirm-withdrawal'
    elif (value['kind'] not in ('new','change') or mismatch or reversed_dates
          or any(not value[k] for k in REQUIRED)
          or any('conflict' in issue.lower() for issue in value['issues'])):
        status,owner,action='needs-information','IT Service Desk','clarify'
    elif value['environment']=='production' or value['permission'] in ('write','admin'):
        status,owner,action='review','Security Review','review-risk-then-owner'
    else:
        status,owner,action='review','System Owner','review-request'
    return {'status':status,'owner':owner,'next_action':action}
