"""Gate model responses before using data; failures never produce stale extractions."""
import json
from access_requests.contracts import validate_extraction

def extract(provider,document_id,message):
    source=getattr(provider,'response_source','mock')
    try:
        response=provider.extract(document_id,message)
        if not isinstance(response,dict):raise ValueError('Malformed provider response: expected object')
        source=response.get('response_source',source)
        if response.get('status')!='completed':
            raise ValueError('Provider response incomplete or interrupted: '+str(response.get('status')))
        if response.get('error'):raise ValueError('Provider returned an error')
        parts=[]
        for item in response.get('output',[]):
            if not isinstance(item,dict):raise ValueError('Malformed output item')
            if item.get('status') not in (None,'completed'):raise ValueError('Provider output item incomplete')
            for content in item.get('content',[]):
                if content.get('type')=='refusal':raise ValueError('Provider refusal; inspect message or retry extraction')
                if content.get('type')=='output_text':parts.append(content['text'])
        if not parts:raise ValueError('Provider response contains no output text')
        value=json.loads(''.join(parts))
        validate_extraction(value,message)
        return {'extraction':value,'error':None,'response_source':source}
    except Exception as error:
        detail=str(error)
        if hasattr(provider,'redact'):detail=provider.redact(detail)
        return {'extraction':None,'error':f'{type(error).__name__}: {detail}; retry the affected document','response_source':source}
