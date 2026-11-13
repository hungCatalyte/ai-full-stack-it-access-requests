"""OpenAI Responses HTTP adapter; transport and credentials can be injected offline."""
import json
import urllib.request
import urllib.error
from pathlib import Path
from access_requests.contracts import ROOT, SCHEMA

class OpenAIProvider:
    def __init__(self, *, credential, model='gpt-5-mini', endpoint='https://api.openai.com/v1/responses', timeout=60, max_output_tokens=4096, transport=None):
        if not credential:raise ValueError('Live mode requires API_KEY')
        if not endpoint.startswith('https://'):raise ValueError('Provider endpoint must use HTTPS')
        self.credential=credential
        self.model=model
        self.endpoint=endpoint
        self.timeout=timeout
        self.max_output_tokens=max_output_tokens
        self.transport=transport or self._http
        self.response_source='openai:'+model

    def request(self,message):
        policy=(ROOT/'materials/office-policy.md').read_text()
        instructions=(ROOT/'access_requests/prompt.txt').read_text()+'\nCompany policy:\n'+policy
        return {'model':self.model,'instructions':instructions,
                'input':[{'role':'user','content':message}], 'store':False,
                'max_output_tokens':self.max_output_tokens,
                'reasoning':{'effort':'low'},
                'text':{'format':{'type':'json_schema','name':'access_request','strict':True,'schema':SCHEMA}}}

    def evidence(self,message):
        return {'endpoint':self.endpoint,'headers':{'Authorization':'Bearer [REDACTED]','Content-Type':'application/json'},
                'request':self.request(message),'timeout_seconds':self.timeout}

    def redact(self,text):
        return str(text).replace(self.credential,'[REDACTED]')

    def extract(self,document_id,message):
        try:
            response=self.transport(self.endpoint,{'Authorization':'Bearer '+self.credential,'Content-Type':'application/json'},self.request(message),self.timeout)
        except Exception as error:
            raise RuntimeError(self.redact(error)) from None
        if isinstance(response,dict) and response.get('model'):
            response=dict(response)
            response['response_source']='openai:'+response['model']
        return response

    @staticmethod
    def _http(url,headers,payload,timeout):
        request=urllib.request.Request(url,json.dumps(payload).encode(),headers,method='POST')
        try:
            with urllib.request.urlopen(request,timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Provider HTTP {error.code}; inspect configuration or retry the document') from None
