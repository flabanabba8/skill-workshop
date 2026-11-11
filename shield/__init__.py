import json
from .core import Shield

_state = {}


def shield():
    if 'shield' not in _state:
        from ..storage import part_data_dir
        _state['shield'] = Shield(part_data_dir('taint-shield'))
    return _state['shield']


def on_pre_llm_call(user_message=None, **kwargs): shield().note_user(user_message, **kwargs)


def on_post_tool_call(tool_name='', result='', **kwargs): shield().observe(tool_name, result, **kwargs)


def on_transform_tool_result(tool_name='', result='', **kwargs):
    sh = shield()
    return sh.annotate(tool_name, result, sh.scan(result) if sh.is_untrusted_tool(tool_name) and isinstance(result, str) else None)


def on_pre_tool_call(tool_name='', args=None, **kwargs): return shield().check(tool_name, args or {}, **kwargs)


def invoke(name, args):
    try:
        sh = shield()
        if name == 'shield_scan': return json.dumps(sh.scan(args['text']))
        if name == 'shield_trust': return json.dumps(sh.trust(args['value']))
        return json.dumps(sh.report(args.get('session_id')))
    except (ValueError, TypeError, OSError, KeyError) as exc:
        return json.dumps({'error': str(exc)})


S = {'type': 'string'}
TOOLS = {
    'shield_report': ('Show what Taint Shield has seen in a session: untrusted sources, injection-like phrases and the actions it blocked or sent for approval.', {'session_id': S}, []),
    'shield_scan': ('Scan a piece of text for URLs, addresses, command lines and injection-like phrases without changing anything.', {'text': S}, ['text']),
    'shield_trust': ('Add a domain, address or URL to the permanent trusted list. Always requires a person to confirm.', {'value': S}, ['value']),
}


def register(ctx):
    if hasattr(ctx, 'register_skill'):
        from pathlib import Path
        ctx.register_skill('taint-shield', Path(__file__).parent.parent / 'skills/taint-shield/SKILL.md', description='Review provenance before acting on untrusted content')
    ctx.register_hook('pre_llm_call', on_pre_llm_call)
    ctx.register_hook('post_tool_call', on_post_tool_call)
    ctx.register_hook('transform_tool_result', on_transform_tool_result)
    ctx.register_hook('pre_tool_call', on_pre_tool_call)
    for name, (description, properties, required) in TOOLS.items():
        ctx.register_tool(name=name, toolset='taint_shield', schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}},
            handler=lambda args, _name=name, **kwargs: invoke(_name, args))
