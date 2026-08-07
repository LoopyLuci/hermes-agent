"""Generate protocol types from v1 JSON Schemas."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parent / 'schema'
RUST_OUT = SCHEMA_DIR.parent.parent.parent / 'rust' / 'protocol' / 'src' / 'v1' / 'generated.rs'
PY_OUT = SCHEMA_DIR.parent.parent.parent / 'python' / 'sdk' / 'src' / 'hermes_worker' / 'generated_protocol.py'

BASE_FIELDS = {
    'protocol_version': ('String', 'str'),
    'message_id': ('String', 'str'),
    'timestamp': ('i64', 'int'),
}


def load_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in SCHEMA_DIR.glob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        title = data.get('title') or path.stem
        properties = {}
        required = []
        const_type = None
        for item in data.get('allOf', []):
            if item.get('type') == 'object':
                properties = item.get('properties', {})
                required = item.get('required', [])
                type_field = properties.get('type', {})
                if type_field.get('const'):
                    const_type = type_field['const']
        schemas[title] = {
            'title': title,
            'properties': properties,
            'required': required,
            'const_type': const_type,
        }
    return schemas


def rust_type(prop: dict[str, Any]) -> str:
    if 'enum' in prop:
        variants = ', '.join(f'"{v}"' for v in prop['enum'])
        return f'String /* {variants} */'
    t = prop.get('type', 'Any')
    if t == 'string':
        return 'String'
    if t == 'integer':
        return 'i64'
    if t == 'boolean':
        return 'bool'
    if t == 'array':
        items = prop.get('items', {})
        inner = rust_type(items)
        return f'Vec<{inner}>'
    if t == 'object':
        return 'serde_json::Value'
    return 'serde_json::Value'


def python_type(prop: dict[str, Any]) -> str:
    if 'enum' in prop:
        return 'str'
    t = prop.get('type', 'Any')
    if t == 'string':
        return 'str'
    if t == 'integer':
        return 'int'
    if t == 'boolean':
        return 'bool'
    if t == 'array':
        items = prop.get('items', {})
        inner = python_type(items)
        return f'list[{inner}]'
    if t == 'object':
        return 'dict[str, Any]'
    return 'Any'


def generate_rust(schemas: dict[str, dict[str, Any]]) -> str:
    lines = [
        '// Auto-generated from x-runtime/protocol/v1/schema/*.json',
        '// Run `python x-runtime/protocol/v1/generate.py` to regenerate.',
        'use serde::{Deserialize, Serialize};',
        '',
    ]
    for name, schema in schemas.items():
        if name == 'EnvelopeBase':
            continue
        const_type = schema.get('const_type')
        lines.append(f'#[derive(Debug, Clone, Serialize, Deserialize)]')
        lines.append(f'pub struct {name} {{')
        for field_name, (rust_t, _) in BASE_FIELDS.items():
            lines.append(f'    pub {field_name}: {rust_t},')
        for prop_name, prop in schema['properties'].items():
            if prop_name in set(BASE_FIELDS) | {'type'}:
                continue
            rust_t = rust_type(prop)
            optional = '' if prop_name in schema['required'] else 'Option<'
            close = '' if prop_name in schema['required'] else '>'
            lines.append(f'    pub {prop_name}: {optional}{rust_t}{close},')
        if const_type:
            lines.append(f'    #[serde(rename = "type")]')
            lines.append(f'    pub kind: String,')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines)


def generate_python(schemas: dict[str, dict[str, Any]]) -> str:
    lines = [
        '"""Auto-generated from x-runtime/protocol/v1/schema/*.json."""',
        'from __future__ import annotations',
        'from dataclasses import dataclass, field',
        'from typing import Any',
        '',
    ]
    for name, schema in schemas.items():
        if name == 'EnvelopeBase':
            continue
        const_type = schema.get('const_type')
        lines.append('')
        lines.append(f'@dataclass')
        lines.append(f'class {name}:')
        for field_name, (_, py_t) in BASE_FIELDS.items():
            lines.append(f'    {field_name}: {py_t}')
        for prop_name, prop in schema['properties'].items():
            if prop_name in set(BASE_FIELDS) | {'type'}:
                continue
            py_t = python_type(prop)
            default = '' if prop_name in schema['required'] else ' = field(default=None)'
            lines.append(f'    {prop_name}: {py_t}{default}')
        if const_type:
            lines.append(f'    kind: str = field(default="{const_type}")')
        else:
            lines.append('    kind: str = field(default="")')
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    schemas = load_schemas()
    RUST_OUT.write_text(generate_rust(schemas), encoding='utf-8')
    PY_OUT.write_text(generate_python(schemas), encoding='utf-8')
    print(f'generated {RUST_OUT}')
    print(f'generated {PY_OUT}')


if __name__ == '__main__':
    main()
