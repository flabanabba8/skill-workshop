"""Deterministic helpers for building skills: resource facts, draft lint, case evidence, revisions. No model calls."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from .retired_policy import DENIED_NAMES, DENIED_TEXT, require_current_workflow

NAME = re.compile(r'^[a-z0-9][a-z0-9-]{2,60}$')
EXEC = re.compile(r'^[A-Za-z0-9_.+-]{1,40}$')
CASES = ('limited-offline', 'capable-gpu-cached', 'hosted-selected')
VERDICTS = ('works', 'degraded', 'blocked')

def _probe_env():
    """Environment for every probe: PATH, HOME and LANG only, so a probed program never sees provider keys from the Hermes environment."""
    return {'PATH': os.environ.get('PATH', ''), 'HOME': str(Path.home()), 'LANG': 'C'}

PROBE = ('python3', 'pip', 'uv', 'node', 'npm', 'git', 'curl', 'ffmpeg', 'ffprobe', 'sox', 'pandoc', 'tesseract', 'docker', 'ollama', 'llama-server', 'whisper-cli')
GENERIC = {'helper', 'utility', 'utilities', 'assistant', 'wrapper', 'general', 'tool', 'tools', 'skill', 'misc', 'stuff', 'generic'}
HEDGE = re.compile(r'(?i)\b(or|e\.g\.|for example|such as|if available|when available|any compatible|alternatives?|discover|example)\b')
MANDATORY = re.compile(r'(?i)\b(must|required?|always|only|mandatory|hard-?coded)\b')
PATH_PERSONAL = re.compile(r'(/home/[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\[^\s\\]+|/root/\S+)')
PROVIDER = re.compile(r'\b(whisper-(?:large|medium|small|base|tiny|v?\d)[\w.-]*|gpt-[\w.-]+|claude-[\w.-]+|gemini-[\w.-]+|glm-[\w.-]+|deepseek-[\w.-]+|[a-z0-9-]+/[a-z0-9][\w.-]*(?:-\d[\w.]*|-instruct|-it))\b', re.I)
HARNESS = re.compile(r'(agents/openai\.yaml|\.codex/|\bCODEX_[A-Z_]+|\bAGENTS\.md\b|\bCLAUDE\.md\b|\$CLAUDE_|\.claude/)')
SIDE = re.compile(r'(?i)\b(pip install|npm install|apt(-get)? install|brew install|curl [^|\n]*\|\s*(ba)?sh|sudo |download|upload|git push|publish|deploy)\b')
CONSENT = re.compile(r'(?i)(approv|confirm|authori[sz]|permission|ask the user|ask before|consent|with the user)')
LINK = re.compile(r'\]\(([^)#\s]+)')
TICK = re.compile(r'`([^`\n]+)`')


def _fm(text):
    lines = text.split('\n')
    if not lines or lines[0].strip() != '---': return None, 0
    for i in range(1, min(len(lines), 40)):
        if lines[i].strip() == '---':
            d = {}
            for ln in lines[1:i]:
                m = re.match(r'^([A-Za-z_-]+):\s*(.*)$', ln)
                if m: d[m.group(1)] = m.group(2).strip().strip('"\'')
            return d, i + 1
    return None, 0


def _hits(lines, rx, skip=()):
    return [{'line': i + 1, 'text': ln.strip()[:160]} for i, ln in enumerate(lines) if i not in skip and rx.search(ln)]


def _row(cid, status, detail, hits=None):
    r = {'check': cid, 'status': status, 'detail': detail}
    if hits: r['lines'] = hits[:8]
    return r


def host_tool_names():
    try:
        from tools.registry import registry
        return set(registry.get_all_tool_names())
    except Exception:
        return None


def lint(text, name=None, base_dir=None, known_tools=None):
    """Return one row per check. status: pass, fail, warn or skipped."""
    lines = text.split('\n'); fm, body_at = _fm(text); rows = []
    skip_fm = set(range(body_at))
    if fm is None: rows.append(_row('frontmatter', 'fail', 'No closing --- frontmatter block at the top of the file', [{'line': 1, 'text': lines[0][:80]}])); fm = {}
    else:
        problems = []
        if not NAME.match(fm.get('name', '')): problems.append('name missing or not lowercase-hyphen slug (3-61 chars)')
        elif name and fm['name'] != name: problems.append(f'frontmatter name {fm["name"]} differs from draft name {name}')
        if not fm.get('description'): problems.append('description missing')
        rows.append(_row('frontmatter', 'fail' if problems else 'pass', '; '.join(problems) or 'name and description present'))
    desc = fm.get('description', ''); words = re.findall(r'[a-z]+', (fm.get('name', '') + ' ' + desc).lower())
    probs = []
    if len(desc) < 40: probs.append('description under 40 characters')
    if len(desc) > 1024: probs.append('description over 1024 characters')
    if not re.search(r'(?i)\b(use (when|for|to|if)|when (the user|asked|you)|triggers?)\b', desc): probs.append('description gives no trigger (say when to use it)')
    if words and sum(w in GENERIC for w in words) * 4 >= len(words): probs.append('mostly generic words; name the concrete task')
    if fm.get('name', '') in DENIED_NAMES: probs.append('name is a retired generic wrapper')
    rows.append(_row('description_quality', 'fail' if probs else 'pass', '; '.join(probs) or 'specific description with a trigger'))
    body = lines[body_at:]
    rows.append(_row('size', 'fail' if len(lines) > 500 else 'warn' if len(lines) > 300 or len(''.join(body).strip()) < 200 else 'pass',
                     f'{len(lines)} lines' if (len(lines) <= 300 and len(''.join(body).strip()) >= 200) else f'{len(lines)} lines; keep 200-ish, move detail to references, and give the body real decisions'))
    pers = _hits(lines, PATH_PERSONAL, skip_fm)
    rows.append(_row('personal_paths', 'fail' if pers else 'pass', 'Home-directory paths tie the skill to one machine; describe how to discover the location' if pers else 'no personal paths', pers))
    prov = [h for h in _hits(lines, PROVIDER, skip_fm)]
    bad = [h for h in prov if MANDATORY.search(h['text']) and not HEDGE.search(h['text'])]
    rows.append(_row('provider_ids', 'fail' if bad else 'warn' if prov else 'pass', 'A model or provider id is presented as mandatory; make it an example chosen after discovery' if bad else 'provider ids appear only as hedged examples' if prov else 'no provider or model ids', bad or prov))
    ok_acc = bool(re.search(r'(?i)(acceptance|done when|success criteria|verify|verification|observable)', '\n'.join(body)))
    rows.append(_row('acceptance', 'pass' if ok_acc else 'fail', 'acceptance wording present' if ok_acc else 'needs observable acceptance checks (how a run proves the goal was met)'))
    ok_deg = bool(re.search(r'(?i)(degraded|fallback|if (it is )?(unavailable|missing)|blocker|cannot supply|not available|setup choice)', text))
    rows.append(_row('degraded_mode', 'pass' if ok_deg else 'fail', 'degraded mode or blocker stated' if ok_deg else 'needs a stated degraded mode or blocker for a missing capability'))
    ret = _hits(lines, DENIED_TEXT, skip_fm)
    rows.append(_row('retired_workflows', 'fail' if ret or fm.get('name', '') in DENIED_NAMES else 'pass', 'depends on a retired workflow' if ret else 'no retired workflow references', ret))
    har = _hits(lines, HARNESS, skip_fm)
    rows.append(_row('harness_neutral', 'warn' if har else 'pass', 'Host-specific files are named; say what the file does so another harness can follow' if har else 'no host-specific file names', har))
    side = [h for h in _hits(lines, SIDE, skip_fm)]
    consent = bool(CONSENT.search(text))
    rows.append(_row('side_effects', 'warn' if side and not consent else 'pass', 'installs, downloads, uploads or publishing appear without any approval step' if side and not consent else 'side effects are absent or tied to approval', side if not consent else None))
    missing = []
    if base_dir is not None:
        root = Path(base_dir)
        for i, ln in enumerate(lines):
            if i in skip_fm: continue
            for t in LINK.findall(ln) + [t for t in TICK.findall(ln) if re.match(r'^(\.{0,2}/)?[\w.-]+(/[\w.-]+)+\.\w{1,5}$', t)]:
                if t.startswith(('http', 'mailto', '/', '~')): continue
                if not (root / t).exists(): missing.append({'line': i + 1, 'text': t})
        rows.append(_row('referenced_files', 'fail' if missing else 'pass', 'referenced files do not exist next to the draft' if missing else 'all referenced files exist', missing))
    else: rows.append(_row('referenced_files', 'skipped', 'no base_dir; saved drafts hold SKILL.md only, so reference files must be inlined or checked with base_dir'))
    ids = {}
    for i, ln in enumerate(lines):
        if i in skip_fm: continue
        for t in TICK.findall(ln):
            if re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$', t): ids.setdefault(t, i + 1)
    known = known_tools if known_tools is not None else host_tool_names()
    if known is None: rows.append(_row('referenced_tools', 'skipped', 'host tool registry not reachable from here'))
    else:
        unk = [{'line': ln, 'text': t} for t, ln in ids.items() if t not in known]
        rows.append(_row('referenced_tools', 'warn' if unk else 'pass', 'snake_case tool names not registered in this host; confirm each exists or say how to discover it' if unk else 'referenced tool names are registered', unk))
    return rows


def _scrub(text):
    # keep the tool version, drop where it lives (home-directory names are private)
    return re.sub(r'(/home|/Users)/[^/\s]+', r'\1/<user>', text)


def resources(include_model_cache=True, extra=()):
    out = {'platform': os.uname().sysname.lower() if hasattr(os, 'uname') else os.name, 'cpu_count': os.cpu_count()}
    try:
        for ln in Path('/proc/meminfo').read_text().splitlines():
            if ln.startswith('MemTotal'): out['ram_gb'] = round(int(ln.split()[1]) / 1048576, 1)
            if ln.startswith('MemAvailable'): out['ram_available_gb'] = round(int(ln.split()[1]) / 1048576, 1)
    except OSError: out['ram_gb'] = None
    out['disk_free_gb'] = round(shutil.disk_usage(Path.home()).free / 1e9, 1)
    exe = {}
    for n in PROBE:
        p = shutil.which(n)
        if not p: exe[n] = None; continue
        try:
            r = subprocess.run([p, '--version'], capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL, env=_probe_env()); exe[n] = {'found': True, 'version': _scrub(((r.stdout or r.stderr).strip().split('\n') or [''])[0][:100])}
        except (OSError, subprocess.SubprocessError): exe[n] = {'found': True, 'version': None}
    for n in list(extra)[:20]:
        if isinstance(n, str) and EXEC.match(n): exe[n] = {'found': bool(shutil.which(n)), 'version': 'not probed (extra names are located, never run)'}
    out['executables'] = exe
    smi = shutil.which('nvidia-smi'); gpus = []
    if smi:
        try:
            r = subprocess.run([smi, '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL, env=_probe_env())
            gpus = []
            for l in r.stdout.splitlines()[:8]:
                m = re.search(r'(\d+)\s*MiB', l)
                if l.strip(): gpus.append({'vendor': 'NVIDIA', 'vram_gb': round(int(m.group(1)) / 1024, 1) if m else None})
        except (OSError, subprocess.SubprocessError): pass
    out['gpus'] = gpus or None; out['gpu_note'] = 'Vendor and memory only (model names are not reported). NVIDIA only via nvidia-smi; None means not detected here, not that no accelerator exists'
    tools = host_tool_names(); out['host_tools'] = sorted(tools)[:300] if tools else None
    try:
        from hermes_constants import get_hermes_home
        sd = get_hermes_home() / 'skills'
        out['host_skills'] = sorted(p.parent.name for p in sd.glob('*/SKILL.md'))[:200] if sd.is_dir() else []
    except Exception: out['host_skills'] = None
    if include_model_cache:
        names = []
        hub = Path(os.environ.get('HF_HOME', Path.home() / '.cache/huggingface')) / 'hub'
        if hub.is_dir(): names += [p.name[8:].replace('--', '/') for p in sorted(hub.glob('models--*'))[:40]]
        man = Path.home() / '.ollama/models/manifests'
        if man.is_dir(): names += ['ollama:' + '/'.join(p.parts[-2:]) for p in sorted(man.glob('*/*/*'))[:40]]
        out['cached_models'] = names[:60]
    out['notice'] = 'Directory and executable names only. No model was loaded and no credential or account store was read.'
    return out


class Drafts:
    def __init__(self, root): self.root = Path(root); self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _dir(self, name):
        if not isinstance(name, str) or not NAME.match(name): raise ValueError('name must be lowercase letters, digits and hyphens (3-61 chars)')
        return self.root / name

    def revisions(self, name):
        d = self._dir(name); return sorted(int(p.name[4:]) for p in d.glob('rev-*') if p.is_dir()) if d.is_dir() else []

    def save(self, name, text, note=''):
        if not isinstance(text, str) or not text.strip(): raise ValueError('text is empty')
        if len(text) > 200000: raise ValueError('draft is over 200000 characters')
        d = self._dir(name); d.mkdir(mode=0o700, exist_ok=True); n = (self.revisions(name) or [0])[-1] + 1
        rd = d / f'rev-{n:04d}'; rd.mkdir(mode=0o700); (rd / 'SKILL.md').write_text(text, encoding='utf-8')
        (rd / 'meta.json').write_text(json.dumps({'revision': n, 'saved_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'note': str(note)[:500]}, indent=1))
        return n, str(rd / 'SKILL.md')

    def get(self, name, revision=None):
        revs = self.revisions(name)
        if not revs: raise ValueError(f'No saved draft named {name}')
        n = revision if revision is not None else revs[-1]
        if n not in revs: raise ValueError(f'Draft {name} has revisions {revs}, not {n}')
        return n, self._dir(name) / f'rev-{n:04d}'

    def cases(self, name, revision):
        n, rd = self.get(name, revision); f = rd / 'cases.json'
        return json.loads(f.read_text()) if f.is_file() else {}

    def record_case(self, name, revision, case, walkthrough, verdict):
        if case not in CASES: raise ValueError(f'case must be one of {list(CASES)}')
        if verdict not in VERDICTS: raise ValueError(f'verdict must be one of {list(VERDICTS)}')
        if not isinstance(walkthrough, str) or len(walkthrough.strip()) < 80: raise ValueError('walkthrough must say, in 80+ characters, which path the skill takes in this case, what it needs and what the result is')
        n, rd = self.get(name, revision); c = self.cases(name, n)
        c[case] = {'verdict': verdict, 'walkthrough': walkthrough[:4000], 'recorded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        (rd / 'cases.json').write_text(json.dumps(c, indent=1), encoding='utf-8')
        return n, [x for x in CASES if x not in c]

    def check(self, name, revision=None, known_tools=None):
        n, rd = self.get(name, revision); text = (rd / 'SKILL.md').read_text(encoding='utf-8')
        rows = lint(text, name, known_tools=known_tools); c = self.cases(name, n); missing = [x for x in CASES if x not in c]
        rows.append(_row('contrasting_cases', 'warn' if missing else 'pass', f'walk-throughs still missing: {missing}' if missing else 'all three contrasting cases recorded for this revision'))
        return n, rows, missing

    def install(self, name, revision, skills_dir, allow_findings=False):
        from .. import skillscan
        n, rows, missing = self.check(name, revision)
        failed = [r['check'] for r in rows if r['status'] == 'fail']
        if failed: raise ValueError(f'Refusing to install: failing checks {failed}')
        if missing: raise ValueError(f'Refusing to install: contrasting cases missing {missing}')
        _, rd = self.get(name, n); text = (rd / 'SKILL.md').read_text(encoding='utf-8'); require_current_workflow(name, text)
        findings = skillscan.scan_skill(text)
        if findings and not allow_findings: raise ValueError(skillscan.refusal(findings))
        target = Path(skills_dir) / name
        if target.exists(): raise ValueError(f'A skill named {name} already exists; nothing was changed')
        target.mkdir(parents=True); (target / 'SKILL.md').write_text(text, encoding='utf-8')
        return {'installed': str(target / 'SKILL.md'), 'name': name, 'revision': n, 'prompt_injection_scan': {'findings': findings, 'summary': skillscan.CLEAN if not findings else f'installed with {len(findings)} finding(s) after the requester asked to and a person approved'}}


def summary(rows):
    return {'ok': not any(r['status'] == 'fail' for r in rows), 'failing': [r['check'] for r in rows if r['status'] == 'fail'], 'warnings': [r['check'] for r in rows if r['status'] == 'warn']}
