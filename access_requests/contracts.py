"""Byte-preserving input and validation for the supplied extraction schema.

This validates the schema's type/properties/required/enum/items/additionalProperties
vocabulary explicitly, rather than claiming to implement arbitrary JSON Schema.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'snapshot.schema.json').read_text())

def load_document(path):
    path = Path(path)
    raw = path.read_bytes()
    export = json.loads(raw.decode('utf-8'))
    if not isinstance(export, dict) or not isinstance(export.get('message'), str):
        raise ValueError('Export must be a JSON object containing a message string')
    return {'document_id':path.name,'source_sha256':hashlib.sha256(raw).hexdigest(),
            'message':export['message'],'filename':str(path),'source_bytes':raw}

def _validate(value, schema, location='extraction'):
    allowed={'type','properties','required','additionalProperties','enum','items'}
    if set(schema)-allowed:
        raise ValueError('Unsupported schema keywords: '+str(sorted(set(schema)-allowed)))
    types=schema.get('type', [])
    types=[types] if isinstance(types,str) else types
    checks={'object':lambda v:isinstance(v,dict),'array':lambda v:isinstance(v,list),
            'string':lambda v:isinstance(v,str),'null':lambda v:v is None}
    if types and not any(checks[k](value) for k in types):
        raise ValueError(f'{location}: expected {types}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{location}: invalid enum value')
    if isinstance(value,dict):
        if set(schema.get('required',[]))-set(value):
            raise ValueError(f'{location}: missing required properties')
        properties=schema.get('properties',{})
        if schema.get('additionalProperties') is False and set(value)-set(properties):
            raise ValueError(f'{location}: additional properties')
        for key, child in properties.items():
            if key in value:_validate(value[key],child,f'{location}.{key}')
    if isinstance(value,list) and 'items' in schema:
        for item in value:_validate(item,schema['items'],location+'[]')

def validate_extraction(value, message):
    _validate(value,SCHEMA)
    if any(quote not in message for quote in value['supporting_quotes']):
        raise ValueError('Supporting quote is not an exact message substring')
    return value
