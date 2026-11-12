"""Offline tests for envelope normalization, diagnose, refine, check and gated install. No model or network."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from tests.miner.test_miner import core, module, make_db
from tests.miner.statedb import Store


class EnvelopeTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.db = str(Path(self.tmp.name) / 'state.db')
    def tearDown(self): self.tmp.cleanup()

    def test_wrapped_calls_are_normalized_to_the_underlying_tool_and_arguments(self):
        make_db(self.db, wrapped=True); sessions = core.load(self.db, 30); top = core.mine(sessions)[0]
        self.assertEqual(top['steps'], ['read_file', 'terminal:git', 'patch', 'terminal:python'])
        step = sessions[0]['steps'][1]; self.assertEqual((step['tool'], step['args']), ('terminal', {'command': 'git status'})); self.assertTrue(step['mapped'])
        name, text = core.draft(top, sessions, self.db)
        self.assertNotIn('"calls"', text); self.assertNotIn('{"', text); self.assertIn('`git status`', text); self.assertIn('path=<path>', text)

    def test_duplicate_calls_of_one_tool_in_a_batch_stay_unmapped(self):
        store = Store(self.db); store.session('d', time.time())
        batch = {'calls': [{'name': 'read_file', 'arguments': {'path': '/a/b/c'}}, {'name': 'read_file', 'arguments': {'path': '/d/e/f'}}]}
        store.msg('d', 'assistant', tool_calls=[{'id': 'k', 'function': {'name': 'tool_call', 'arguments': json.dumps(batch)}}])
        store.msg('d', 'tool', '{}', tool_name='read_file', call_id='k'); store.close()
        step = core.load(self.db, 30)[0]['steps'][0]; self.assertEqual((step['args'], step['mapped']), ({}, False)); self.assertIn('/d/e/f', step['raw'])  # guard still sees every inner call


class RefineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = str(Path(self.tmp.name) / 'state.db'); make_db(self.db, flaky_every=3)
        self.sessions = core.load(self.db, 30); self.found = core.mine(self.sessions)[0]; self.name, self.text = core.draft(self.found, self.sessions, self.db)
        self.props = core.Proposals(Path(self.tmp.name) / 'p'); ev = {**{k: v for k, v in self.found.items() if not k.startswith('_')}, 'support_sessions': self.found['_support'], 'holdout_sessions': self.found['_hold']}
        self.pid = self.props.save(self.name, self.text, ev); self.skills = Path(self.tmp.name) / 'skills'; self.skills.mkdir()
    def tearDown(self): self.tmp.cleanup()

    def good(self):
        return (f"---\nname: {self.name}\ndescription: Use when asked to fix a bug and confirm the tests pass: read the file, check git state, patch it, then run the tests.\n---\n\n# Fix a bug and run tests\n\n"
                "## Steps\n\n1. `read_file` - read the file you will change\n2. `terminal:git` - check the working tree state\n3. `patch` - apply the smallest fix\n4. `terminal:python` - run the project's tests with its own runner\n")

    def ctx(self): return core.context(self.props, self.pid, self.db)

    def test_diagnose_is_bounded_redacted_and_keeps_the_verdict_unchanged(self):
        n, ev, sup, hold = self.ctx(); d = core.diagnose(n, self.text, ev, sup, hold)
        self.assertEqual(d['mining']['verdict'], self.found['verdict']); self.assertEqual(d['mining']['consistency'], self.found['consistency'])
        codes = {p['problem'] for p in d['structural_problems']}; self.assertIn('vague_trigger_description', codes); self.assertIn('unreviewed_marker', codes)
        self.assertLessEqual(len(json.dumps(d)), core.MAX_DIAGNOSE); self.assertLessEqual(len(d['failure_evidence']), 5)
        self.assertTrue(d['failure_evidence']); self.assertNotIn('/home/someone', json.dumps(d))
        flagged = core.diagnose(n, self.text + '\nSee /home/someone/x and sk-' + 'Qz9Lm2Xa' * 4 + ' using claude-opus-9\n', ev, sup, hold)
        self.assertNotIn('Qz9Lm2Xa', json.dumps(flagged)); self.assertNotIn('/home/someone', json.dumps(flagged)); self.assertIn('provider_or_model_id', {p['problem'] for p in flagged['structural_problems']})

    def test_diagnose_flags_a_malformed_sample(self):
        n, ev, sup, hold = self.ctx(); bad = self.text.replace('`read_file`', '`read_file` - typical use: `{"calls":[{"name":"read_f`', 1)
        self.assertIn('malformed_sample', {p['problem'] for p in core.diagnose(n, bad, ev, sup, hold)['structural_problems']})

    def test_refine_preserves_the_original_bytes_and_rejects_retired_text(self):
        d = self.props.dir(self.pid); before = {f.name: f.read_bytes() for f in d.iterdir() if f.is_file()}
        self.assertEqual(self.props.refine(self.pid, self.good(), 'fixed trigger'), 1); self.assertEqual(self.props.refine(self.pid, self.good() + '\nMore.\n', 'x'), 2)
        self.assertEqual({f.name: f.read_bytes() for f in d.iterdir() if f.is_file()}, before); self.assertEqual(self.props.revision(self.pid, 0)[1], self.text)
        with self.assertRaisesRegex(ValueError, 'identical'): self.props.refine(self.pid, self.good() + '\nMore.\n')
        self.assertEqual(self.props.revisions(self.pid), [1, 2])

    def test_check_passes_a_good_revision_and_fails_a_bad_one(self):
        n, ev, sup, hold = self.ctx(); r = core.check(n, self.good(), ev, sup, hold)
        self.assertTrue(r['passed'], r); self.assertEqual({c['check'] for c in r['checks']}, {'frontmatter', 'retired_policy', 'no_leaked_values', 'tools_in_evidence', 'holdout_replay'})
        bad = self.good().replace('terminal:python', 'browser_navigate').replace('Use when', 'Use when /home/someone/proj and').replace('name: ' + self.name, 'name: other-name')
        r = core.check(n, bad, ev, sup, hold); self.assertFalse(r['passed']); failed = {c['check'] for c in r['checks'] if c['ok'] is False}
        self.assertTrue({'frontmatter', 'no_leaked_values', 'tools_in_evidence', 'holdout_replay'} <= failed)

    def test_weak_verdict_is_not_upgraded(self):
        n, ev, sup, hold = self.ctx(); self.assertEqual(ev['verdict'], 'weak'); r = core.check(n, self.good(), ev, sup, hold)
        self.assertEqual(r['mining_verdict'], 'weak'); self.assertIn('not a quality guarantee', r['notice']); self.assertEqual(core.diagnose(n, self.good(), ev, sup, hold)['mining']['verdict'], 'weak')

    def test_install_refuses_unchecked_stale_and_failing_revisions_but_installs_a_checked_one(self):
        rev = self.props.refine(self.pid, self.good())
        with self.assertRaisesRegex(ValueError, 'not been checked'): self.props.install(self.pid, self.skills)
        n, ev, sup, hold = self.ctx(); self.props.save_check(self.pid, rev, self.good(), core.check(n, self.good(), ev, sup, hold))
        rev2 = self.props.refine(self.pid, self.good().replace('smallest', 'tiniest')); self.props.save_check(self.pid, rev2, 'stale text', {'passed': True})
        with self.assertRaisesRegex(ValueError, 'not been checked'): self.props.install(self.pid, self.skills, rev2)
        rev3 = self.props.refine(self.pid, self.good().replace('smallest', 'safest').replace('terminal:python', 'browser_navigate')); self.props.save_check(self.pid, rev3, self.props.revision(self.pid, rev3)[1], core.check(n, self.props.revision(self.pid, rev3)[1], ev, sup, hold))
        with self.assertRaisesRegex(ValueError, 'failed its checks'): self.props.install(self.pid, self.skills, rev3)
        self.assertFalse((self.skills / self.name).exists())
        out = self.props.install(self.pid, self.skills, rev); self.assertEqual(out['revision'], rev); self.assertEqual((self.skills / self.name / 'SKILL.md').read_text(), self.good())

    def test_tool_handlers_round_trip_and_install_still_needs_approval(self):
        self.assertEqual(module.on_pre_tool_call(tool_name='miner_install')['action'], 'approve')
        for t in ('miner_diagnose', 'miner_refine', 'miner_check'): self.assertIsNone(module.on_pre_tool_call(tool_name=t))
        module._paths = lambda: (self.db, self.props, self.skills)
        r = json.loads(module.invoke('miner_refine', {'proposal_id': self.pid, 'skill_text': self.good(), 'notes': 'n'})); self.assertEqual(r['revision'], 1)
        c = json.loads(module.invoke('miner_check', {'proposal_id': self.pid})); self.assertTrue(c['passed'], c); d = json.loads(module.invoke('miner_diagnose', {'proposal_id': self.pid, 'revision': 0})); self.assertIn('structural_problems', d)
        self.assertEqual(json.loads(module.invoke('miner_install', {'proposal_id': self.pid}))['revision'], 1)
        self.assertIn('error', json.loads(module.invoke('miner_check', {'proposal_id': self.pid, 'revision': 9})))


if __name__ == '__main__': unittest.main()
