"""Skill Guard: scan every skill before it is installed or used, including skills from other people."""
import json
from pathlib import Path

from .core import Guard

_state = {}


def guard():
    if 'guard' not in _state:
        from ..storage import part_data_dir
        _state['guard'] = Guard(part_data_dir('skill-guard'))
    return _state['guard']


def _safe(fn, *a):
    try: return fn(*a)
    except Exception: return None   # a guard error must never break Hermes; the install gates and the shield still run


def on_pre_tool_call(tool_name='', args=None, **kwargs):
    if tool_name == 'skillguard_decide': return {'action': 'approve', 'message': 'Skill Guard: this records your decision about one skill version (approve it so it can be used, or quarantine it so it cannot). A person must confirm, so a skill cannot approve itself.', 'rule_key': 'skillguard-decide'}
    return _safe(guard().on_pre_tool_call, tool_name, args)


def on_post_tool_call(tool_name='', args=None, result='', **kwargs): _safe(guard().on_post_tool_call, tool_name, args, result)


def on_transform_tool_result(tool_name='', args=None, result='', **kwargs): return _safe(guard().on_skill_view, tool_name, args, result)


def on_pre_llm_call(user_message=None, **kwargs):
    g = guard()
    return _safe(g.on_user_message, user_message) or _safe(g.next_notice)


def on_skill_lifecycle(action='', skill_name='', **kwargs): _safe(guard().on_skill_lifecycle, action, skill_name)


def invoke(name, args, **ctx):
    try:
        if name == 'skillguard_decide': return json.dumps(guard().decide(args['skill'], args['decision']))
        return json.dumps(guard().scan_installed(args.get('include_clean', True)))
    except (ValueError, TypeError, OSError, KeyError) as exc:
        return json.dumps({'error': str(exc)})


S = {'type': 'string'}
TOOLS = {
    'skillguard_scan_installed': ('Scan every skill already installed (Hermes skills folder and any external skill folders) for prompt injection and list each as clean, approved, quarantined or flagged, with file and line for every finding. Reads files only; changes nothing.', {'include_clean': {'type': 'boolean'}}, []),
    'skillguard_decide': ('Record the user\'s decision about one installed skill, for its exact current version: approve (use it as it is despite the findings) or quarantine (never hand its instructions to the agent). Always requires a person to confirm.', {'skill': S, 'decision': {'type': 'string', 'enum': ['approve', 'quarantine']}}, ['skill', 'decision']),
}


def register(ctx):
    if hasattr(ctx, 'register_skill'):
        ctx.register_skill('skill-guard', Path(__file__).parent.parent / 'skills/skill-guard/SKILL.md', description='Scan skills from other people before they are installed or used')
    ctx.register_hook('pre_tool_call', on_pre_tool_call)
    ctx.register_hook('post_tool_call', on_post_tool_call)
    ctx.register_hook('transform_tool_result', on_transform_tool_result)
    ctx.register_hook('pre_llm_call', on_pre_llm_call)
    ctx.register_hook('on_skill_lifecycle', on_skill_lifecycle)
    for name, (description, properties, required) in TOOLS.items():
        ctx.register_tool(name=name, toolset='skill_guard', schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}},
            handler=lambda args, _name=name, **kwargs: invoke(_name, args, **kwargs))
