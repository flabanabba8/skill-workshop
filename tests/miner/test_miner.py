import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

root = Path(__file__).parents[2]
from tests.fixture_suite import suite
from tests.miner.statedb import Store
module = suite.miner
core = module.core
SECRET = 'sk-' + 'Qz9Lm2Xa' * 4


def make_db(path, flaky_every=0, wrapped=False):
    store = Store(path); msg = store.msg
    now = time.time(); n = 0

    def call(sid, tool, args, result):
        nonlocal n; n += 1; cid = f'c{n}'
        fn = {'name': 'tool_call', 'arguments': json.dumps({'calls': [{'name': tool, 'arguments': args}]})} if wrapped else {'name': tool, 'arguments': json.dumps(args)}
        msg(sid, 'assistant', tool_calls=json.dumps([{'id': cid, 'function': fn}])); msg(sid, 'tool', json.dumps(result), tool_name=tool, call_id=cid)

    ok = {'output': 'ok', 'exit_code': 0}
    for i in range(9):   # the repeated workflow: read, git status, patch, pytest
        sid = f's{i:02d}'; store.session(sid, now - 1000 + i)
        msg(sid, 'user', f'Fix the bug in module{i}.py and make sure the tests pass /home/someone/proj{i}' + (f' key {SECRET}' if i == 0 else ''))
        call(sid, 'read_file', {'path': f'/home/someone/proj{i}/m{i}.py'}, {'content': 'x'}); call(sid, 'terminal', {'command': 'git status'}, ok)
        call(sid, 'patch', {'path': f'm{i}.py', 'old_string': 'a', 'new_string': 'b'}, {'success': True})
        call(sid, 'terminal', {'command': 'cd /home/someone/proj && python -m pytest -q'}, {'output': '1 failed', 'exit_code': 1} if flaky_every and i % flaky_every == 0 else ok)
    for i in range(4):   # unrelated sessions
        sid = f'r{i}'; store.session(sid, now - 500 + i); msg(sid, 'user', 'something else')
        call(sid, 'web_search', {'q': f'topic {i}'}, {'results': []}); call(sid, 'web_extract', {'url': f'https://e{i}.example'}, {'content': 'x'})
    store.close()


def make_chore_db(path):
    """Eight chats; every one opens with the same housekeeping calls. Four repeat one chore (meeting notes -> action list)."""
    store = Store(path)
    now = time.time(); n = 0

    def call(sid, tool, args, result):
        nonlocal n; n += 1; cid = f'c{n}'
        store.msg(sid, 'assistant', tool_calls=[{'id': cid, 'function': {'name': tool, 'arguments': json.dumps(args)}}])
        store.msg(sid, 'tool', json.dumps(result), tool_name=tool, call_id=cid)
    ok = {'output': 'ok', 'exit_code': 0}
    asks = ['Turn my meeting notes from Monday into an action list', 'Please turn the meeting notes into an action list with owners', 'Can you turn these meeting notes into an action list', 'Turn the meeting notes for the budget call into an action list']
    others = ['Find a good ramen place', 'What changed in the python release', 'Summarise this article for me', 'Look up the weather for Friday']
    for i, ask in enumerate(asks + others):
        sid = f'c{i}'; store.session(sid, now - 1000 + i)
        store.msg(sid, 'user', ask)
        call(sid, 'skills_list', {}, {'skills': []}); call(sid, 'search_files', {'pattern': '*.md'}, {'files': []}); call(sid, 'skill_view', {'name': 'notes'}, {'success': True})
        if i < 4:
            call(sid, 'read_file', {'path': f'/home/someone/notes/meeting{i}.md'}, {'content': 'x'}); call(sid, 'write_file', {'path': f'/home/someone/notes/actions{i}.md', 'content': '- a'}, {'success': True})
        else:
            call(sid, 'web_search', {'q': ask}, {'results': []}); call(sid, 'web_extract', {'url': f'https://e{i}.example'}, {'content': 'x'}); call(sid, 'read_file', {'path': f'/tmp/other{i}.txt'}, {'content': 'x'})
    store.close()


class ChoreNotHousekeeping(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = str(Path(self.tmp.name) / 'chores.db'); make_chore_db(self.db)
        self.sessions = core.load(self.db, 30); self.found = core.mine(self.sessions, min_support=3, lo=3, hi=6)
    def tearDown(self): self.tmp.cleanup()

    def test_four_chats_of_one_chore_each_opening_with_the_same_housekeeping_yield_the_chore(self):
        top = self.found[0]
        self.assertEqual(top['steps'], ['read_file', 'write_file']); self.assertEqual(top['sessions'], 4); self.assertEqual(top['verdict'], 'recommend')
        self.assertGreaterEqual(top['holdout_hits'], 1)
        for p in self.found: self.assertFalse(any(core.is_housekeeping(t) for t in p['steps']), p['steps'])
        self.assertTrue({'meeting', 'notes', 'action', 'list'} <= set(top['request_terms'])); self.assertEqual(top['file_types'], ['md'])
        self.assertIn('skills_list', top['housekeeping_skipped'])

    def test_housekeeping_alone_never_forms_a_pattern(self):
        hk = [{**s, 'steps': [x for x in s['steps'] if core.is_housekeeping(x['token'])]} for s in self.sessions]
        self.assertEqual(core.mine(hk, min_support=3, lo=3, hi=6), [])

    def test_skill_is_named_and_described_from_the_request_not_the_tool_names(self):
        name, text = core.draft(self.found[0], self.sessions, self.db)
        self.assertRegex(name, core.NAME); self.assertIn('meeting', name); self.assertIn('notes', name); self.assertNotIn('skills', name); self.assertNotIn('workflow', name)
        fm = core.frontmatter(text); self.assertIn('meeting notes', fm['description'].lower()); self.assertTrue(30 <= len(fm['description']) <= 500)
        self.assertIn('`read_file`', text); self.assertIn('`write_file`', text); self.assertNotIn('1. `skills_list`', text); self.assertIn('housekeeping', text)
        self.assertNotIn('/home/someone', text)

    def test_held_out_check_and_replay_still_apply_to_the_chore(self):
        props = core.Proposals(Path(self.tmp.name) / 'p'); top = self.found[0]; name, text = core.draft(top, self.sessions, self.db)
        pid = props.save(name, text, {k: v for k, v in top.items() if not k.startswith('_')} | {'support_sessions': top['_support'], 'holdout_sessions': top['_hold']})
        n, ev, sup, hold = core.context(props, pid, self.db); result = core.check(n, text, ev, sup, hold)
        self.assertTrue([c for c in result['checks'] if c['check'] == 'holdout_replay'][0]['ok']); self.assertTrue(result['passed'], result)

    def test_a_chore_with_no_write_step_and_no_shared_wording_is_not_promoted_from_two_steps(self):
        sess = [{'id': f's{i}', 'request': f'unrelated thing {i}', 'steps': [{'token': 'read_file', 'failed': False, 'args': {}}, {'token': 'web_search', 'failed': False, 'args': {}}]} for i in range(6)]
        self.assertEqual(core.mine(sess, min_support=3, lo=3, hi=6), [])


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
