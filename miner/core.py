"""Mine repeated tool workflows from the session database (read-only) and draft reviewable skills. Proposes only."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid
from collections import Counter
from .retired_policy import require_current_workflow

ID = re.compile(r'^[0-9a-f]{12}$')
NAME = re.compile(r'^[a-z0-9][a-z0-9-]{2,60}$')
TRIVIAL = {'read_file', 'search_files', 'terminal:ls', 'terminal:cat', 'terminal:echo', 'terminal:cd', 'terminal:pwd', 'terminal:head', 'terminal:tail', 'terminal:grep', 'terminal:find'}
# Calls that open almost any session (find a skill, search for a tool, list or search files) say nothing about the chore the user repeated.
HOUSEKEEPING = {'skills_list', 'skill_view', 'search_files', 'list_files', 'tool_search', 'search_tools', 'list_tools', 'tool_details', 'get_tool', 'describe_tool', 'session_search', 'todo', 'terminal:ls', 'terminal:pwd', 'terminal:cd', 'terminal:which', 'terminal:echo', 'terminal:tree'}
DISCOVERY_NAME = re.compile(r'^(?:skills?_(?:list|view|search)|(?:list|search|find|describe|get)_(?:files?|tools?|skills?|docs?|schemas?)|tool_(?:search|details?|info|docs?|help)|.*_(?:tool|schema)_(?:details?|info|docs?))$')
WRITES = {'write_file', 'patch', 'edit_file', 'create_file', 'append_file', 'skill_manage', 'terminal:tee', 'terminal:sed', 'terminal:mv', 'terminal:cp', 'terminal:mkdir', 'terminal:git'}
STOP = set('a an and are as at be but by can could do does for from get give had has have help how i if in into is it its just let like make me my need not of on one or our out please that the their them then there these they this to turn up us use want was we what when which who will with would you your all any some also new now each every after before about over again more most other same than too very via should create write run using put take show tell'.split())
REDACT = [re.compile(p) for p in (r'sk-[A-Za-z0-9_-]{16,}', r'gh[pousr]_[A-Za-z0-9]{20,}', r'xox[abprs]-[A-Za-z0-9-]{10,}', r'AKIA[0-9A-Z]{16}', r'(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}',
                                   r'(?i)(api[_-]?key|token|secret|password)["\']?\s*[:=]\s*["\']?[A-Za-z0-9._~+/=-]{10,}')]


def redact(text):
    for r in REDACT: text = r.sub('[redacted]', text)
    return text


def abstract(text, limit=160):
    text = redact(text)
    text = re.sub(r'https?://\S+', '<url>', text); text = re.sub(r'(?<![\w/])(~|/home/[^/\s]+|/Users/[^/\s]+|/root|/tmp|/var|/etc|/opt|/srv|\.{1,2})?(/[\w.@+-]+){2,}', '<path>', text)
    text = re.sub(r'\b[0-9a-f]{12,}\b', '<id>', text); text = re.sub(r'\b\d{3,}\b', '<n>', text)
    return text[:limit]


def cmd0(command):
    c = command.strip()
    c = re.sub(r'^(cd\s+\S+\s*(&&|;)\s*)+', '', c)
    c = re.sub(r'^((\w+=\S+)\s+)+', '', c)
    m = re.match(r'([A-Za-z0-9_.+-]{1,30})', os.path.basename(c.split()[0]) if c.split() else '')
    return m.group(1) if m else 'cmd'


def token(tool, args):
    if tool == 'terminal' and isinstance(args, dict) and isinstance(args.get('command'), str): return 'terminal:' + cmd0(args['command'])
    return tool


def failed(content):
    try: d = json.loads(content)
    except (ValueError, TypeError): return False
    if isinstance(d, dict):
        if d.get('error'): return True
        c = d.get('exit_code'); return isinstance(c, int) and not isinstance(c, bool) and c != 0
    return False


def parse_args(value):
    if isinstance(value, str):
        try: value = json.loads(value) if value.strip() else {}
        except ValueError: return {}
    return value if isinstance(value, dict) else {}


def envelope_entries(args):
    """Hermes tool_call bridge: {"calls": [{"name", "arguments"}]} or the legacy single {"name", "arguments"} (see tools/tool_search_validation.py)."""
    raw = args.get('calls')
    if raw is None and str(args.get('name') or '').strip(): raw = [{'name': args['name'], 'arguments': args.get('arguments')}]
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except ValueError: return []
    if isinstance(raw, dict): raw = [raw]
    if not isinstance(raw, list): return []
    return [(str(e['name']).strip(), parse_args(e.get('arguments'))) for e in raw if isinstance(e, dict) and str(e.get('name') or '').strip()]


def resolve_call(tool, outer_name, outer_args, inner):
    """Return (tool, args, mapped, raw). A batch envelope is mapped to the result's tool only when exactly one inner call has that name."""
    if inner is None: return tool, outer_args, True, outer_args
    if tool == 'tool_call' and len(inner) == 1: tool = inner[0][0]
    hits = [a for n, a in inner if n == tool]
    if len(hits) == 1: return tool, hits[0], True, hits[0]
    return tool, {}, False, [{'name': n, 'arguments': a} for n, a in inner]  # ambiguous or absent: do not guess, but keep the raw text for the retired-workflow guard


def error_text(content):
    try: d = json.loads(content)
    except (ValueError, TypeError): return abstract(str(content or '').replace('\n', ' '), 120)
    if isinstance(d, dict): return abstract(str(d.get('error') or d.get('output') or d.get('message') or d)[-300:].replace('\n', ' '), 120)
    return ''


def load(db, days, limit=400, ids=None):
    p = Path(db)
    if not p.is_file(): raise ValueError('No session database found')
    cutoff = time.time() - days * 86400
    con = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=5)
    try:
        if ids is None: ids = [r[0] for r in con.execute('SELECT id FROM sessions WHERE started_at >= ? ORDER BY started_at LIMIT ?', (cutoff, limit))]
        else:
            ids = list(ids)[:limit]; marks = ','.join('?' * len(ids))
            have = {r[0] for r in con.execute(f'SELECT id FROM sessions WHERE id IN ({marks})', ids)} if ids else set(); ids = [i for i in ids if i in have]
        sessions = []
        for sid in ids:
            calls, steps, request = {}, [], ''
            for role, tool_calls, tool_name, content, call_id in con.execute('SELECT role, tool_calls, tool_name, content, tool_call_id FROM messages WHERE session_id = ? ORDER BY id', (sid,)):
                if role == 'user' and not request and content: request = abstract(' '.join(str(content).split()), 300)
                if role == 'assistant' and tool_calls:
                    try:
                        for c in json.loads(tool_calls):
                            f = c.get('function') or {}; args = parse_args(f.get('arguments')); name = f.get('name')
                            calls[c.get('id')] = (name, args, envelope_entries(args) if name == 'tool_call' else None)
                    except (ValueError, AttributeError, TypeError): pass
                elif role == 'tool' and tool_name:
                    outer = calls.get(call_id, (None, {}, None)); tool, args, mapped, raw = resolve_call(tool_name, *outer)
                    bad = failed(content or '')
                    steps.append({'token': token(tool, args), 'failed': bad, 'args': args, 'tool': tool, 'mapped': mapped, 'raw': tool + '\n' + json.dumps(raw, ensure_ascii=False, default=str), 'err': error_text(content) if bad else ''})
            if steps: sessions.append({'id': sid, 'steps': steps, 'request': request})
    finally: con.close()
    return sessions


def collapse(tokens):
    out = []
    for t in tokens:
        if not out or out[-1] != t: out.append(t)
    return out


def grams(seq, lo, hi): return {tuple(seq[i:i + n]) for n in range(lo, hi + 1) for i in range(len(seq) - n + 1)}


def contains(seq, pattern):
    n = len(pattern); return any(tuple(seq[i:i + n]) == pattern for i in range(len(seq) - n + 1))


def pid(pattern): return hashlib.sha256('|'.join(pattern).encode()).hexdigest()[:12]


def is_housekeeping(tok): return tok in HOUSEKEEPING or bool(DISCOVERY_NAME.match(tok))


def terms_of(text): return [w for w in re.findall(r"[a-z][a-z'-]{2,}", (text or '').lower()) if w not in STOP and not w.startswith('<')]


def shared_terms(requests, share=0.6, limit=6):
    """Words that most of the repeated requests contain, in the order the first request uses them."""
    reqs = [terms_of(r) for r in requests if r]
    if len(reqs) < 2: return []
    count = Counter(w for r in reqs for w in set(r)); need = max(2, -(-int(share * 100) * len(reqs) // 100))
    out = []
    for w in reqs[0]:
        if count[w] >= need and w not in out: out.append(w)
    return out[:limit]


def shared_file_types(step_lists, share=0.6):
    per = []
    for steps in step_lists:
        exts = set()
        for x in steps:
            for k, v in (x.get('args') or {}).items():
                if k in ('path', 'file_path', 'file', 'filename', 'output', 'output_path', 'input') and isinstance(v, str):
                    m = re.search(r'\.([A-Za-z0-9]{1,5})$', v.strip())
                    if m: exts.add(m.group(1).lower())
        per.append(exts)
    if len(per) < 2: return []
    c = Counter(e for ex in per for e in ex); need = max(2, -(-int(share * 100) * len(per) // 100))
    return sorted(e for e, n in c.items() if n >= need)


def mine(sessions, min_support=3, lo=3, hi=6):
    """Patterns are built from the steps that belong to the chore: housekeeping calls (finding a skill, searching tools or files) that open
    almost every session are left out. A pattern of only two steps is accepted when it writes something and the requests share wording.
    Candidates are ranked by what is specific to the job: shared request words, shared file types and write/edit steps."""
    core_steps = {s['id']: [x for x in s['steps'] if not is_housekeeping(x['token'])] for s in sessions}
    seen_hk = sorted({x['token'] for s in sessions for x in s['steps'] if is_housekeeping(x['token'])})
    seqs = [(s['id'], collapse([x['token'] for x in core_steps[s['id']]])) for s in sessions]
    train = [x for i, x in enumerate(seqs) if i % 3 != 2]; hold = [x for i, x in enumerate(seqs) if i % 3 == 2]
    short = min(lo, 2); count = Counter()
    for _, seq in train:
        for g in grams(seq, short, hi): count[g] += 1
    def writes(g): return sum(t in WRITES for t in g)
    cands = [g for g, c in count.items() if c >= min_support and not all(t in TRIVIAL for t in g) and (len(set(g)) >= 3 or (writes(g) and len(set(g)) >= 2))]
    keep = []
    for g in sorted(cands, key=lambda g: (-len(g), -count[g])):
        if not any(len(k) > len(g) and count[k] == count[g] and contains(list(k), g) for k in keep): keep.append(g)
    by_id = {s['id']: s for s in sessions}; out = []
    for g in keep:
        support = [sid for sid, seq in seqs if contains(seq, g)]
        terms = shared_terms([by_id[sid].get('request', '') for sid in support])
        if len(g) < lo and not (writes(g) and len(terms) >= 2): continue
        ok = 0
        for sid in support:
            toks = core_steps[sid]; flat = [x['token'] for x in toks]; n = len(g)
            for i in range(len(flat) - n + 1):
                if tuple(collapse(flat[i:i + n])) == g or tuple(flat[i:i + n]) == g:
                    ok += not any(x['failed'] for x in toks[i:i + n]); break
        h_hits = sum(contains(seq, g) for _, seq in hold)
        consistency = ok / len(support) if support else 0
        verdict = 'recommend' if len(support) >= min_support and consistency >= 0.75 and (h_hits >= 1 or not hold) else 'weak'
        types = shared_file_types([core_steps[sid] for sid in support]); spec = 3 * min(len(terms), 4) + 2 * min(len(types), 2) + 2 * min(writes(g), 2)
        out.append({'pattern_id': pid(g), 'steps': list(g), 'sessions': len(support), 'train_sessions': count[g], 'holdout_sessions_total': len(hold), 'holdout_hits': h_hits, 'consistency': round(consistency, 2), 'verdict': verdict,
                    'request_terms': terms, 'file_types': types, 'specificity': spec, 'housekeeping_skipped': seen_hk, '_support': support, '_hold': [sid for sid, _ in hold]})
    out.sort(key=lambda p: (p['verdict'] != 'recommend', -p['specificity'], -(p['sessions'] * len(p['steps']))))
    return out


def first_user_messages(db, session_ids, n=3):
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=5); out = []
    try:
        for sid in session_ids:
            r = con.execute("SELECT content FROM messages WHERE session_id = ? AND role = 'user' ORDER BY id LIMIT 1", (sid,)).fetchone()
            if r and r[0]: out.append(abstract(r[0].strip().replace('\n', ' '), 200))
            if len(out) >= n: break
    finally: con.close()
    return out


def raw_text(step):
    return step.get('raw') or (step.get('tool', '') + '\n' + json.dumps(step.get('args', {}), ensure_ascii=False, default=str))


def sample(tok, args):
    """A short plain-text example that is never truncated JSON."""
    if not isinstance(args, dict) or not args: return ''
    if tok.startswith('terminal') and isinstance(args.get('command'), str): return abstract(args['command'].replace('`', "'"), 100)
    return ' '.join(f"{k}={abstract(str(v).replace('`', chr(39)), 40)}" for k, v in list(args.items())[:4] if isinstance(v, (str, int, float, bool)))[:100]


def draft(pattern, sessions, db):
    # Check raw call text (nested envelope arguments included) before path abstraction can hide a removed dependency.
    for session in sessions:
        if session['id'] in pattern['_support']:
            for step in session['steps']:
                if step['token'] in pattern['steps']: require_current_workflow(text=raw_text(step))
    by_id = {s['id']: s for s in sessions}; steps = []
    for i, tok in enumerate(pattern['steps']):
        examples = Counter()
        for sid in pattern['_support']:
            for x in by_id[sid]['steps']:
                if x['token'] == tok:
                    examples[sample(tok, x['args'])] += 1; break
        steps.append((tok, [e for e, _ in examples.most_common(2) if e]))
    terms = pattern.get('request_terms') or []
    if len(terms) >= 2: slug = '-'.join(terms[:4]); name = re.sub(r'[^a-z0-9-]+', '', slug)[:50].strip('-')
    else: name = ''
    if not NAME.match(name):
        slug = re.sub(r'[^a-z0-9]+', '-', '-'.join(t.replace('terminal:', '') for t in pattern['steps'][:4]).lower()).strip('-')[:40]; name = f'workflow-{slug}'
    triggers = first_user_messages(db, pattern['_support'])
    if len(terms) >= 2 and triggers: desc = f'Use when the user asks for the same chore as in {pattern["sessions"]} earlier chats, for example "{triggers[0][:110]}". Steps drafted from those chats; review and edit before use.'
    else: desc = f"Repeat the {' then '.join(t.replace('terminal:', '') for t in pattern['steps'][:3])} workflow you have used in {pattern['sessions']} earlier sessions. Draft: review and edit before use."
    trig_lines = [f'- "{t}"' for t in triggers] or ['- (no request text available)']
    lines = ['---', f'name: {name}', f'description: {desc}', '---', '',
             '# Draft skill (mined, unreviewed)', '', f"Mined from {pattern['sessions']} of your sessions; held-out check: {pattern['holdout_hits']} of {pattern['holdout_sessions_total']} unseen sessions repeated it; steps succeeded together in {int(pattern['consistency'] * 100)} percent of supporting sessions.", '',
             '## When this came up', *trig_lines, '', '## Steps seen, in order', '']
    if pattern.get('housekeeping_skipped'): lines.insert(lines.index('## Steps seen, in order') + 1, 'Chats of this kind usually open with housekeeping calls (' + ', '.join(pattern['housekeeping_skipped'][:6]) + '); they are not part of the chore and are left out.'); lines.insert(lines.index('## Steps seen, in order') + 2, '')
    for i, (tok, ex) in enumerate(steps, 1):
        lines.append(f'{i}. `{tok}`' + (' - typical use: ' + '; '.join(f'`{e}`' for e in ex) if ex else ''))
    lines += ['', '## Before using', '', '- These steps are what you did, not a statement of what is correct. Check each one and remove anything specific to a single project.', '- Arguments above are abstracted (paths, URLs and numbers replaced); fill in the real ones.']
    return name, '\n'.join(lines) + '\n'


MAX_REVISIONS, MAX_TEXT, MAX_NOTES, MAX_DIAGNOSE = 8, 20000, 2000, 8000
PERSONAL = re.compile(r'/home/[^/\s`]+|/Users/[^/\s`]+|[A-Za-z]:\\Users\\[^\\\s`]+|~/\.(?:ssh|aws|hermes|codex|claude|gnupg)\b|[\w.+-]+@[\w-]+\.[\w.-]+')
PROVIDER = re.compile(r'\b(?:openai|anthropic|nvidia|z-ai|google|moonshotai|cx)/[\w.-]+|\b(?:gpt|claude|gemini|glm|kimi|deepseek|qwen|llama)-[\w.]+')
STEP_LINE = re.compile(r'^\s*\d+\.\s+`([^`]+)`', re.M)
NOTICE = 'These checks describe the draft structure and a replay of its step order on held-out sessions. They are not a quality guarantee, and the mining verdict is unchanged.'


def sha(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()


def step_tokens(text): return STEP_LINE.findall(text)


def frontmatter(text):
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not m: return None
    return dict((k.strip(), v.strip()) for k, _, v in (ln.partition(':') for ln in m.group(1).split('\n')) if k.strip())


def subsequence(seq, steps):
    it = iter(seq); return all(any(t == s for t in it) for s in steps)


def window(steps, pattern):
    n = len(pattern)
    for i in range(len(steps) - n + 1):
        flat = [x['token'] for x in steps[i:i + n]]
        if tuple(flat) == pattern or tuple(collapse(flat)) == pattern: return i, i + n
    return None


def diagnose(name, text, evidence, support, hold):
    """Bounded, redacted failure and quality context for one proposal. The mining verdict and numbers are returned unchanged."""
    fm = frontmatter(text) or {}; desc = fm.get('description', ''); problems = []

    def add(code, detail): problems.append({'problem': code, 'detail': abstract(detail, 200)})
    if not fm: add('no_frontmatter', 'The draft has no valid --- frontmatter block.')
    if len(desc) < 60 or 'Draft:' in desc or 'review and edit' in desc or not re.search(r'\b(?:when|use)\b', desc, re.I): add('vague_trigger_description', 'The description should say when to use the skill (what the user asks for), not that it is a draft.')
    if 'mined, unreviewed' in text: add('unreviewed_marker', 'The "mined, unreviewed" heading is still present.')
    for span in re.findall(r'typical use: (.*)', text):
        for sm in re.findall(r'`([^`]*)`', span):
            if sm.startswith(('{', '[')):
                try: json.loads(sm)
                except ValueError: add('malformed_sample', 'A typical-use sample is truncated or malformed JSON: ' + sm[:60])
            if '"calls"' in sm or '"arguments"' in sm: add('envelope_wrapper_in_sample', 'A sample still contains the tool_call wrapper.')
    for m in sorted(set(PERSONAL.findall(text)))[:5]: add('personal_value', 'A personal path or address is written into the skill: ' + m)
    for m in sorted(set(PROVIDER.findall(text)))[:5]: add('provider_or_model_id', 'A provider or model id appears; it must be an adaptive choice, not mandatory: ' + m)
    have, want = step_tokens(text), evidence.get('steps', [])
    if not have: add('no_steps', 'No numbered step lines of the form 1. `tool` were found.')
    elif [t for t in want if t not in have]: add('missing_steps', 'Mined steps absent from the text: ' + ', '.join(t for t in want if t not in have))
    pat = tuple(want); unmapped = sum(1 for s in support for x in s['steps'] if x['token'] in pat and not x.get('mapped', True))
    if unmapped: add('unmapped_batched_calls', f'{unmapped} steps came from batched tool_call envelopes with duplicate calls of the same tool; their arguments were left unmapped, so their examples are missing.')
    ev = []
    for n, sess in enumerate(support[:5], 1):
        sess = {**sess, 'steps': [x for x in sess['steps'] if not is_housekeeping(x['token'])]}
        w = window(sess['steps'], pat) if pat else None
        if not w: continue
        items = []
        for i in range(w[0], min(len(sess['steps']), w[1] + 3)):
            x = sess['steps'][i]
            if x['failed']: items.append({'step': x['token'], 'where': 'in_sequence' if i < w[1] else 'just_after', 'error': x.get('err', '')[:120]})
            elif i > 0 and sess['steps'][i - 1]['failed'] and sess['steps'][i - 1]['token'] == x['token']: items.append({'step': x['token'], 'where': 'retry_succeeded'})
        if items: ev.append({'support_session': n, 'events': items[:4]})
    out = {'mining': {k: evidence.get(k) for k in ('pattern_id', 'steps', 'sessions', 'train_sessions', 'holdout_sessions_total', 'holdout_hits', 'consistency', 'verdict')}, 'structural_problems': problems[:12], 'failure_evidence': ev,
           'notice': 'Evidence comes only from this proposal\'s selected sessions, redacted and size-limited. Diagnosis points at problems; it does not prove the draft is correct. The mining verdict is unchanged.'}
    while len(json.dumps(out)) > MAX_DIAGNOSE and out['failure_evidence']: out['failure_evidence'].pop()
    return out


def check(name, text, evidence, support, hold):
    """Deterministic checks of one revision's text. Each check is reported separately."""
    fm = frontmatter(text); checks = []

    def add(label, ok, detail): checks.append({'check': label, 'ok': ok, 'detail': detail})
    if not fm: add('frontmatter', False, 'Missing --- frontmatter block.')
    else:
        bad = [m for m, c in (('name differs from the proposal name or is invalid', fm.get('name') == name and bool(NAME.match(name))), ('description missing or not 30-500 characters', 30 <= len(fm.get('description', '')) <= 500)) if not c]
        add('frontmatter', not bad, '; '.join(bad) or 'name and description are valid.')
    try: require_current_workflow(name, text); add('retired_policy', True, 'No retired workflow referenced.')
    except ValueError as exc: add('retired_policy', False, str(exc))
    leaks = [m for m in PERSONAL.findall(text)] + [r.pattern[:20] for r in REDACT if r.search(text)]
    add('no_leaked_values', not leaks, 'No personal paths, addresses or secret patterns.' if not leaks else f'{len(leaks)} personal or secret-like values found.')
    seen = {x['tool'] for s in support + hold for x in s['steps']} | {x['token'] for s in support + hold for x in s['steps']}; steps = step_tokens(text)
    unknown = [t for t in steps if t not in seen]
    add('tools_in_evidence', bool(steps) and not unknown, 'Every step tool appears in the mined sessions.' if steps and not unknown else ('No numbered step lines of the form 1. `tool` found.' if not steps else 'Not seen in the mined sessions: ' + ', '.join(unknown)))
    if not hold: add('holdout_replay', None, 'Skipped: no held-out sessions are available in the history.')
    else:
        hits = sum(subsequence(collapse([x['token'] for x in s['steps']]), steps) for s in hold) if steps else 0
        base = evidence.get('holdout_hits', 0) or 0
        add('holdout_replay', hits >= max(1, base), f'The refined step order occurs in {hits} of {len(hold)} held-out sessions (the mined pattern had {base}).')
    return {'checks': checks, 'passed': all(c['ok'] is not False for c in checks), 'mining_verdict': evidence.get('verdict'), 'notice': NOTICE}


def context(props, proposal_id, db):
    """Selected authorized history for one proposal: its supporting and held-out sessions only."""
    name, _ = props.get(proposal_id); ev = props.evidence(proposal_id)
    if ev.get('support_sessions') is not None:
        by = {s['id']: s for s in load(db, 0, ids=list(ev['support_sessions']) + list(ev.get('holdout_sessions', [])))}
        sup, hold = ev['support_sessions'], ev.get('holdout_sessions', [])
    else:  # proposal from 0.1.0: re-derive the same sessions by pattern id
        sessions = load(db, 365); found = {p['pattern_id']: p for p in mine(sessions)}.get(ev.get('pattern_id'))
        if not found: raise ValueError('This proposal predates 0.2.0 and its sessions cannot be re-derived from current history; run miner_scan and miner_propose again')
        by = {s['id']: s for s in sessions}; sup, hold = found['_support'], found['_hold']
    return name, ev, [by[i] for i in sup if i in by], [by[i] for i in hold if i in by]


class Proposals:
    def __init__(self, root): self.root = Path(root); self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def dir(self, proposal_id):
        if not isinstance(proposal_id, str) or not ID.match(proposal_id) or not (self.root / proposal_id / 'SKILL.md').is_file(): raise ValueError('Unknown proposal')
        return self.root / proposal_id

    def save(self, name, text, evidence):
        pid_ = uuid.uuid4().hex[:12]; d = self.root / pid_; d.mkdir(mode=0o700)
        (d / 'SKILL.md').write_text(text, encoding='utf-8'); (d / 'evidence.json').write_text(json.dumps(evidence, indent=1), encoding='utf-8'); (d / 'name.txt').write_text(name)
        return pid_

    def get(self, proposal_id):
        d = self.dir(proposal_id); return (d / 'name.txt').read_text(), (d / 'SKILL.md').read_text(encoding='utf-8')

    def evidence(self, proposal_id): return json.loads((self.dir(proposal_id) / 'evidence.json').read_text(encoding='utf-8'))

    def revisions(self, proposal_id):
        rd = self.dir(proposal_id) / 'revisions'
        return sorted(int(m.group(1)) for f in rd.glob('r*.md') if (m := re.fullmatch(r'r(\d+)\.md', f.name))) if rd.is_dir() else []

    def revision(self, proposal_id, n=None):
        """Text of revision n (0 is the untouched original); None means the latest."""
        revs = self.revisions(proposal_id)
        if n is None: n = revs[-1] if revs else 0
        if n == 0: return 0, self.get(proposal_id)[1]
        if n not in revs: raise ValueError('Unknown revision')
        return n, (self.dir(proposal_id) / 'revisions' / f'r{n}.md').read_text(encoding='utf-8')

    def refine(self, proposal_id, text, notes='', new_name=None):
        name, _ = self.get(proposal_id)
        if new_name is not None:
            if not isinstance(new_name, str) or not NAME.match(new_name): raise ValueError('name must be a lowercase skill name (letters, digits, hyphens, 3-61 characters)')
            name = new_name
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT: raise ValueError(f'skill_text must be non-empty text of at most {MAX_TEXT} characters')
        require_current_workflow(name, text)
        revs = self.revisions(proposal_id)
        if len(revs) >= MAX_REVISIONS: raise ValueError(f'At most {MAX_REVISIONS} revisions per proposal; install or start a new proposal')
        if text == self.revision(proposal_id)[1]: raise ValueError('The revision is identical to the previous text; nothing was saved')
        n = (revs[-1] if revs else 0) + 1; rd = self.dir(proposal_id) / 'revisions'; rd.mkdir(mode=0o700, exist_ok=True)
        if new_name is not None and new_name != self.get(proposal_id)[0]:
            d = self.dir(proposal_id)
            if not (d / 'original-name.txt').exists(): (d / 'original-name.txt').write_text(self.get(proposal_id)[0])
            (d / 'name.txt').write_text(new_name)
        (rd / f'r{n}.md').write_text(text, encoding='utf-8'); (rd / f'r{n}.notes.txt').write_text(redact(str(notes or ''))[:MAX_NOTES], encoding='utf-8')
        return n

    def save_check(self, proposal_id, n, text, result):
        rd = self.dir(proposal_id) / 'revisions'; rd.mkdir(mode=0o700, exist_ok=True)
        (rd / f'r{n}.check.json').write_text(json.dumps({'revision': n, 'sha256': sha(text), **result}, indent=1), encoding='utf-8')

    def pick(self, proposal_id, revision=None):
        name, original = self.get(proposal_id); n, text = self.revision(proposal_id, revision) if (revision is not None or self.revisions(proposal_id)) else (0, original)
        return name, n, text

    def install(self, proposal_id, skills_dir, revision=None, allow_findings=False):
        from .. import skillscan
        name, n, text = self.pick(proposal_id, revision)
        if n:
            f = self.dir(proposal_id) / 'revisions' / f'r{n}.check.json'
            rec = json.loads(f.read_text(encoding='utf-8')) if f.is_file() else None
            if not rec or rec.get('sha256') != sha(text): raise ValueError(f'Revision {n} has not been checked; run miner_check first. Nothing was changed')
            if not rec.get('passed'): raise ValueError(f'Revision {n} failed its checks; refine it and check again. Nothing was changed')
        if not NAME.match(name): raise ValueError('Proposal name is not a valid skill name')
        require_current_workflow(name, text)
        findings = skillscan.scan_skill(text)
        if findings and not allow_findings: raise ValueError(skillscan.refusal(findings))
        target = Path(skills_dir) / name
        if target.exists(): raise ValueError(f'A skill named {name} already exists; nothing was changed')
        target.mkdir(parents=True); (target / 'SKILL.md').write_text(text, encoding='utf-8')
        return {'installed': str(target / 'SKILL.md'), 'name': name, 'revision': n, 'prompt_injection_scan': {'findings': findings, 'summary': skillscan.CLEAN if not findings else f'installed with {len(findings)} finding(s) after the requester asked to and a person approved'}}
