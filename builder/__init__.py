import json
from . import core


def _store():
    from ..storage import part_data_dir
    return core.Drafts(part_data_dir('first-principles-skill-builder') / 'drafts')


def on_pre_tool_call(tool_name='', **kwargs):
    if tool_name == 'skillbuilder_install':
        return {'action': 'approve', 'message': 'First Principles Skill Builder: this installs a checked draft into your skills folder. A person must read the draft and confirm.', 'rule_key': 'skillbuilder-install'}
    return None


def invoke(name, args):
    try:
        if name == 'skillbuilder_resources':
            return json.dumps(core.resources(args.get('include_model_cache', True), args.get('extra_executables', [])))
        if name == 'skillbuilder_check' and args.get('text') is None and not args.get('name'):
            raise ValueError('give the draft name (a saved draft) or text (unsaved text) to check')
        s = _store()
        if name == 'skillbuilder_save':
            n, path = s.save(args['name'], args['text'], args.get('note', ''))
            return json.dumps({'name': args['name'], 'revision': n, 'path': path, 'notice': 'Saved as a new revision; earlier revisions are untouched. Nothing was installed.'})
        if name == 'skillbuilder_check':
            if args.get('text') is not None:
                rows = core.lint(args['text'], base_dir=args.get('base_dir')); return json.dumps({'checks': rows, **core.summary(rows), 'notice': 'Unsaved text. Structural lint only; it cannot judge whether the skill works.'})
            n, rows, missing = s.check(args['name'], args.get('revision'))
            return json.dumps({'name': args['name'], 'revision': n, 'checks': rows, **core.summary(rows), 'cases_missing': missing, 'ready_to_install': core.summary(rows)['ok'] and not missing, 'notice': 'Structural lint plus recorded walk-throughs. It cannot judge whether the skill works.'})
        if name == 'skillbuilder_case':
            n, missing = s.record_case(args['name'], args.get('revision'), args['case'], args['walkthrough'], args['verdict'])
            return json.dumps({'name': args['name'], 'revision': n, 'recorded': args['case'], 'cases_missing': missing})
        if name == 'skillbuilder_install':
            from hermes_constants import get_hermes_home
            return json.dumps(s.install(args['name'], args.get('revision'), get_hermes_home() / 'skills'))
        raise ValueError('unknown tool')
    except (ValueError, TypeError, OSError, KeyError, ImportError) as exc:
        return json.dumps({'error': str(exc)})


S = {'type': 'string'}
REV = {'type': 'integer', 'minimum': 1}
TOOLS = {
    'skillbuilder_resources': ('Report this machine\'s CPU count, RAM, free disk, GPU vendor and memory (NVIDIA via nvidia-smi), common executables with versions, cached model names, and the host\'s registered tools and skills. Names only: loads no model, reads no credentials.', {'include_model_cache': {'type': 'boolean'}, 'extra_executables': {'type': 'array', 'items': S, 'maxItems': 20}}, []),
    'skillbuilder_save': ('Save a draft SKILL.md as a new numbered revision under the plugin data folder. Never overwrites an earlier revision and installs nothing.', {'name': S, 'text': S, 'note': S}, ['name', 'text']),
    'skillbuilder_check': ('Check a saved draft revision (or unsaved text) and report each check separately with offending lines: frontmatter, description quality, size, personal paths, provider ids, acceptance, degraded mode, retired workflows, harness neutrality, side effects, referenced files and tools, and recorded contrasting cases.', {'name': S, 'revision': REV, 'text': S, 'base_dir': S}, []),
    'skillbuilder_case': ('Record your walk-through of one contrasting case for a draft revision: limited-offline, capable-gpu-cached or hosted-selected. Returns which cases are still missing.', {'name': S, 'revision': REV, 'case': {'type': 'string', 'enum': list(core.CASES)}, 'walkthrough': S, 'verdict': {'type': 'string', 'enum': list(core.VERDICTS)}}, ['name', 'case', 'walkthrough', 'verdict']),
    'skillbuilder_install': ('Install a checked draft revision as a skill. Refuses failing checks, missing contrasting cases and overwrites, and always requires a person to confirm.', {'name': S, 'revision': REV}, ['name']),
}


def register(ctx):
    if hasattr(ctx, 'register_skill'):
        from pathlib import Path
        ctx.register_skill('first-principles-skill-builder', Path(__file__).parent.parent / 'skills/first-principles-skill-builder/SKILL.md', description='Build, check and improve skills that adapt to the resources that actually exist')
    ctx.register_hook('pre_tool_call', on_pre_tool_call)
    for name, (description, properties, required) in TOOLS.items():
        ctx.register_tool(name=name, toolset='skill_builder', schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}},
            handler=lambda args, _name=name, **kwargs: invoke(_name, args))
