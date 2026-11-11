import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest

root = Path(__file__).parents[2]
from tests.fixture_suite import suite
module = suite.miner
core = module.core
SECRET = 'sk-' + 'Qz9Lm2Xa' * 4


def make_db(path, flaky_every=0, wrapped=False):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE sessions (id TEXT, started_at REAL)'); con.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT)')
    now = time.time(); n = 0

    def msg(sid, role, content=None, tool_calls=None, tool_name=None, call_id=None): con.execute('INSERT INTO messages (session_id, role, content, tool_calls, tool_name, tool_call_id) VALUES (?,?,?,?,?,?)', (sid, role, content, tool_calls, tool_name, call_id))

    def call(sid, tool, args, result):
        nonlocal n; n += 1; cid = f'c{n}'
        fn = {'name': 'tool_call', 'arguments': json.dumps({'calls': [{'name': tool, 'arguments': args}]})} if wrapped else {'name': tool, 'arguments': json.dumps(args)}
        msg(sid, 'assistant', tool_calls=json.dumps([{'id': cid, 'function': fn}])); msg(sid, 'tool', json.dumps(result), tool_name=tool, call_id=cid)

    ok = {'output': 'ok', 'exit_code': 0}
    for i in range(9):   # the repeated workflow: read, git status, patch, pytest
        sid = f's{i:02d}'; con.execute('INSERT INTO sessions VALUES (?,?)', (sid, now - 1000 + i))
        msg(sid, 'user', f'Fix the bug in module{i}.py and make sure the tests pass /home/someone/proj{i}' + (f' key {SECRET}' if i == 0 else ''))
        call(sid, 'read_file', {'path': f'/home/someone/proj{i}/m{i}.py'}, {'content': 'x'}); call(sid, 'terminal', {'command': 'git status'}, ok)
        call(sid, 'patch', {'path': f'm{i}.py', 'old_string': 'a', 'new_string': 'b'}, {'success': True})
        call(sid, 'terminal', {'command': 'cd /home/someone/proj && python -m pytest -q'}, {'output': '1 failed', 'exit_code': 1} if flaky_every and i % flaky_every == 0 else ok)
    for i in range(4):   # unrelated sessions
        sid = f'r{i}'; con.execute('INSERT INTO sessions VALUES (?,?)', (sid, now - 500 + i)); msg(sid, 'user', 'something else')
        call(sid, 'web_search', {'q': f'topic {i}'}, {'results': []}); call(sid, 'web_extract', {'url': f'https://e{i}.example'}, {'content': 'x'})
    con.commit(); con.close()


class MinerTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.db = str(Path(self.tmp.name) / 'state.db'); make_db(self.db)
    def tearDown(self): self.tmp.cleanup()

    def mined(self, **kw):
        s = core.load(self.db, 30); return s, core.mine(s, **kw)

    def test_finds_the_repeated_workflow_and_checks_it_on_held_out_sessions(self):
        sessions, found = self.mined(min_support=3); top = found[0]
        self.assertEqual(top['steps'], ['read_file', 'terminal:git', 'patch', 'terminal:python']); self.assertEqual((top['sessions'], top['verdict']), (9, 'recommend'))
        self.assertGreaterEqual(top['holdout_hits'], 1); self.assertEqual(top['consistency'], 1.0)

    def test_subpatterns_with_the_same_support_are_folded_into_the_longest(self):
        _, found = self.mined(min_support=3); self.assertEqual(len([p for p in found if p['sessions'] == 9]), 1)

    def test_a_flaky_workflow_is_marked_with_its_real_success_rate(self):
        make_db(self.db2 if hasattr(self, 'db2') else str(Path(self.tmp.name) / 'flaky.db'), flaky_every=2)
        s = core.load(str(Path(self.tmp.name) / 'flaky.db'), 30); top = core.mine(s, min_support=3)[0]; self.assertLess(top['consistency'], 0.7)

    def test_too_little_support_finds_nothing_and_unrelated_sessions_do_not_form_patterns(self):
        self.assertEqual([p for p in self.mined(min_support=12)[1]], []); self.assertTrue(all('web_search' not in p['steps'] for p in self.mined(min_support=3)[1] if p['sessions'] > 4))

    def test_draft_is_abstracted_and_redacted_and_lists_the_steps_in_order(self):
        sessions, found = self.mined(min_support=3); name, text = core.draft(found[0], sessions, self.db)
        self.assertNotIn(SECRET, text); self.assertNotIn('/home/someone', text); self.assertIn('[redacted]', text); self.assertIn('<path>', text)
        self.assertLess(text.index('`read_file`'), text.index('`terminal:python`')); self.assertRegex(name, core.NAME); self.assertIn('not a statement of what is correct', text)

    def test_install_needs_a_real_proposal_refuses_overwrite_and_never_touches_other_skills(self):
        sessions, found = self.mined(min_support=3); name, text = core.draft(found[0], sessions, self.db)
        props = core.Proposals(Path(self.tmp.name) / 'p'); pid = props.save(name, text, {}); skills = Path(self.tmp.name) / 'skills'; skills.mkdir()
        self.assertTrue(Path(props.install(pid, skills)['installed']).is_file())
        with self.assertRaisesRegex(ValueError, 'already exists'): props.install(pid, skills)
        with self.assertRaises(ValueError): props.install('../../x', skills)
        with self.assertRaises(ValueError): props.get('0' * 12)

    def test_refine_can_give_the_proposal_a_human_name_which_check_and_install_then_use(self):
        text = '---\nname: workflow-a-b-c\ndescription: Use when the user asks for the thing; draft text for a unit test of naming.\n---\n\n1. `read_file`\n'
        props = core.Proposals(Path(self.tmp.name) / 'p2'); pid = props.save('workflow-a-b-c', text, {})
        with self.assertRaises(ValueError): props.refine(pid, text.replace('workflow-a-b-c', 'Bad Name'), new_name='Bad Name')
        n = props.refine(pid, text.replace('workflow-a-b-c', 'meeting-notes-to-actions'), 'renamed', new_name='meeting-notes-to-actions')
        self.assertEqual(props.get(pid)[0], 'meeting-notes-to-actions'); self.assertEqual((props.dir(pid) / 'original-name.txt').read_text(), 'workflow-a-b-c')
        rev, revised = props.revision(pid); self.assertEqual(rev, n)
        result = core.check(props.get(pid)[0], revised, {}, [], []); self.assertTrue([c for c in result['checks'] if c['check'] == 'frontmatter'][0]['ok'])
        props.save_check(pid, rev, revised, {'passed': True})
        skills = Path(self.tmp.name) / 'skills2'; skills.mkdir()
        self.assertEqual(props.install(pid, skills)['name'], 'meeting-notes-to-actions')
    def test_database_is_read_only_and_install_requires_approval_via_the_hook(self):
        before = Path(self.db).read_bytes(); core.load(self.db, 30); self.assertEqual(Path(self.db).read_bytes(), before)
        self.assertEqual(module.on_pre_tool_call(tool_name='miner_install')['action'], 'approve'); self.assertIsNone(module.on_pre_tool_call(tool_name='miner_scan'))
        with self.assertRaises(ValueError): core.load('/nonexistent/state.db', 30)


if __name__ == '__main__': unittest.main()
