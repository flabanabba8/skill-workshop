"""Scan a skill (SKILL.md and any bundled text files) for prompt injection before it is installed.

Uses the shield's own detection (the same phrase list, secret-path, egress, persistence and
command patterns shield_scan uses), applied line by line so every finding has a line number.
Ordinary skills that show shell commands in their own steps are not flagged: a command is
only reported when it sends data out, touches a local secret, changes a login/startup file,
or pipes a download into a shell.
"""
from pathlib import Path
import re

from .shield import core as sh

MAX_FILE = 200000
MAX_FILES = 40
TEXT_SUFFIXES = {'.md', '.txt', '.sh', '.py', '.json', '.yaml', '.yml', '.toml', '.js', '.ts', '.html', '.cfg', '.ini', ''}
_HIDDEN = [0x200b, 0x200c, 0x200d, 0x2060, 0xfeff] + list(range(0x2061, 0x2065)) + list(range(0x202a, 0x202f)) + list(range(0x2066, 0x206a))  # zero-width and direction-control characters
HIDDEN_CHARS = re.compile('[' + ''.join(map(chr, _HIDDEN)) + ']')
HTML_COMMENT = re.compile(r'<!--(.*?)-->', re.S)
PIPE_TO_SHELL = re.compile(r'\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh(?=\s*(?:$|[;&)`\s]))', re.I)
INSTRUCTION_WORDS = re.compile(r'\b(run|execute|send|email|upload|ignore|do not|don\'t|copy|read|curl|wget|delete|install)\b', re.I)


# Phrases that ordinary skills legitimately contain are left out: a bare mention of "system prompt",
# and "send ... to <url or address>" unless the line also names data being sent.
PHRASES = [(rx, p) for rx, p in zip(sh.PHRASE_RES, sh.PHRASES) if p != 'system prompt']
SENDS_DATA = re.compile(r'\b(key|token|password|secret|credential|cookie|ssh|history|files?|data|contents?)\b', re.I)


def _secret(line):
    # a secret FILE or dump; an environment variable passed to the API it belongs to is ordinary
    return any(not m.group(0).startswith('$') for m in sh.SECRET_PATH.finditer(line))


def _line_findings(line, hidden_context=False):
    out = []
    for rx, p in PHRASES:
        m = rx.search(line)
        if m and (not p.startswith('(send|email') or SENDS_DATA.search(line)): out.append(('injection-like instruction', m.group(0).strip()[:80]))
    cmd_like = bool(sh.COMMAND_LINE.search(line)) or '`' in line or hidden_context
    secret, egress, stage, persist = _secret(line), sh.EGRESS.search(line), sh.STAGE.search(line), sh.PERSIST.search(line)
    if secret and egress and cmd_like: out.append(('command that sends a local secret out', line.strip()[:100]))
    elif secret and stage and cmd_like and re.search(r'\b(cp|mv|rsync|tar|zip|7z|dd)\b', line, re.I): out.append(('command that copies a local secret', line.strip()[:100]))
    elif persist and cmd_like and (egress or stage): out.append(('command that changes a login or startup file', line.strip()[:100]))
    if PIPE_TO_SHELL.search(line): out.append(('command that pipes a download into a shell', line.strip()[:100]))
    return out


def scan_text(text, source='SKILL.md'):
    """Return a list of findings: {file, line, kind, excerpt}."""
    findings = []; seen = set(); text = text[:MAX_FILE]
    def add(line, kind, excerpt):
        key = (line, kind, excerpt)
        if key not in seen: seen.add(key); findings.append({'file': source, 'line': line, 'kind': kind, 'excerpt': excerpt})
    for i, line in enumerate(text.splitlines(), 1):
        if HIDDEN_CHARS.search(line): add(i, 'hidden text (zero-width or direction-control characters)', repr(HIDDEN_CHARS.sub(lambda m: '<U+%04X>' % ord(m.group(0)), line.strip()))[:100])
        for kind, ex in _line_findings(line): add(i, kind, ex)
    for m in HTML_COMMENT.finditer(text):
        body = m.group(1); start = text.count('\n', 0, m.start()) + 1
        if INSTRUCTION_WORDS.search(body) and ((any(r.search(body) for r, _ in PHRASES) or sh.SECRET_PATH.search(body) or sh.EGRESS.search(body) or sh.COMMAND_LINE.search(body) or sh.URL.search(body))):
            add(start, 'hidden text (instruction inside an HTML comment)', ' '.join(body.split())[:100])
    return findings


def scan_skill(text, extra_files=None):
    """SKILL.md text plus optional {name: text} bundled files."""
    findings = scan_text(text, 'SKILL.md')
    for name, body in (extra_files or {}).items(): findings += scan_text(body, name)
    return findings


def scan_path(path):
    """A SKILL.md file, a single text file, or a skill folder (SKILL.md plus bundled text files)."""
    p = Path(path).expanduser()
    if not p.exists(): raise ValueError('path does not exist')
    files = [p] if p.is_file() else sorted(f for f in p.rglob('*') if f.is_file() and '.git' not in f.parts)
    findings = []; scanned = []; skipped = []
    for f in files[:MAX_FILES]:
        rel = f.name if p.is_file() else str(f.relative_to(p))
        if f.suffix.lower() not in TEXT_SUFFIXES: skipped.append(rel); continue
        try: body = f.read_bytes()[:MAX_FILE].decode('utf-8')
        except (OSError, UnicodeDecodeError): skipped.append(rel); continue
        scanned.append(rel); findings += scan_text(body, rel)
    if len(files) > MAX_FILES: skipped.append(f'{len(files) - MAX_FILES} more files not read (limit {MAX_FILES})')
    return {'files_scanned': scanned, 'files_skipped': skipped, 'findings': findings}


CLEAN = 'scanned for prompt injection: no findings'


def describe(findings):
    return '; '.join(f"{f['file']} line {f['line']}: {f['kind']} ({f['excerpt']})" for f in findings)


def refusal(findings):
    return (f'Not installed: the draft failed the prompt-injection scan with {len(findings)} finding(s): ' + describe(findings) +
            '. Fix the draft (remove or rewrite those lines) and try again. If you have read each finding and still want it, call the install again with allow_findings=true: a person is then asked to approve, and the approval text lists these findings.')


def install_gate(findings, allow, approve_message, rule_key):
    """pre_tool_call result for an install tool: block on findings, approve (findings in the text) on override, plain approve when clean."""
    if not findings: return {'action': 'approve', 'message': approve_message + ' ' + CLEAN.capitalize() + '.', 'rule_key': rule_key}
    if not allow: return {'action': 'block', 'message': refusal(findings)}
    return {'action': 'approve', 'message': approve_message + f' WARNING: the prompt-injection scan found {len(findings)} problem(s) and the requester asked to install anyway: ' + describe(findings) + '. Approve only if you have read these lines and they are fine.', 'rule_key': rule_key + ':findings'}
