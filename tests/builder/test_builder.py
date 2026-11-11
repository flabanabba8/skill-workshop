import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

root = Path(__file__).parents[2]
from tests.fixture_suite import suite
module = suite.builder
core = module.core
BAD = (root / 'tests/fixtures/bad.md').read_text(); GOOD = (root / 'tests/fixtures/good.md').read_text()
HOST = {'read_file', 'terminal'}


def by(rows): return {r['check']: r for r in rows}


class Ctx:
    def __init__(self): self.tools = {}; self.hooks = {}; self.skills = {}
    def register_tool(self, **kw): self.tools[kw['name']] = kw
    def register_hook(self, name, fn): self.hooks[name] = fn
    def register_skill(self, name, path, description=''): self.skills[name] = Path(path)


class LintTests(unittest.TestCase):
    def test_bad_draft_fails_each_check_with_its_line(self):
        r = by(core.lint(BAD, 'helper', base_dir=root / 'tests/fixtures', known_tools=HOST))
        for c in ('description_quality', 'personal_paths', 'provider_ids', 'acceptance', 'degraded_mode', 'referenced_files'): self.assertEqual(r[c]['status'], 'fail', c)
        for c in ('harness_neutral', 'side_effects', 'referenced_tools'): self.assertEqual(r[c]['status'], 'warn', c)
        self.assertEqual(r['personal_paths']['lines'][0]['line'], 8)
        self.assertEqual(r['referenced_files']['lines'][0]['text'], 'references/notes.md')
        self.assertEqual(r['referenced_tools']['lines'][0]['text'], 'transcribe_everything')
        self.assertEqual(r['frontmatter']['status'], 'pass')

    def test_improved_draft_passes(self):
        rows = core.lint(GOOD, 'timestamped-transcript', base_dir=root, known_tools=HOST)
        self.assertEqual([r for r in rows if r['status'] in ('fail', 'warn')], [])
        self.assertTrue(core.summary(rows)['ok'])

    def test_frontmatter_problems_and_name_mismatch(self):
        r = by(core.lint('no frontmatter at all', 'abc'))
        self.assertEqual(r['frontmatter']['status'], 'fail')
        r = by(core.lint(GOOD, 'other-name', known_tools=HOST)); self.assertEqual(r['frontmatter']['status'], 'fail')

    def test_mandatory_provider_fails_but_hedged_example_only_warns(self):
        hedge = GOOD + '\nUse e.g. gpt-4o-mini-transcribe or any compatible one.\n'
        self.assertEqual(by(core.lint(hedge, known_tools=HOST))['provider_ids']['status'], 'warn')
        hard = GOOD + '\nYou must use gpt-4o-mini-transcribe.\n'
        self.assertEqual(by(core.lint(hard, known_tools=HOST))['provider_ids']['status'], 'fail')

    def test_size_and_unavailable_registry(self):
        r = by(core.lint(GOOD + '\nx\n' * 600, known_tools=HOST)); self.assertEqual(r['size']['status'], 'fail')
        self.assertEqual(by(core.lint(GOOD, known_tools=HOST))['referenced_files']['status'], 'skipped')


class StoreTests(unittest.TestCase):
    def test_revisions_never_overwrite_and_cases_are_per_revision(self):
        with tempfile.TemporaryDirectory() as d:
            s = core.Drafts(Path(d) / 'drafts')
            n1, p1 = s.save('timestamped-transcript', BAD); n2, p2 = s.save('timestamped-transcript', GOOD, 'fixed')
            self.assertEqual((n1, n2), (1, 2)); self.assertNotEqual(p1, p2)
            self.assertEqual(Path(p1).read_text(), BAD); self.assertEqual(s.revisions('timestamped-transcript'), [1, 2])
            walk = 'Takes the smallest local model on CPU, needs ffmpeg, result: transcript with timestamps, slow but complete.'
            n, missing = s.record_case('timestamped-transcript', 2, 'limited-offline', walk, 'degraded')
            self.assertEqual(missing, ['capable-gpu-cached', 'hosted-selected'])
            self.assertEqual(s.cases('timestamped-transcript', 1), {})
            n, rows, missing = s.check('timestamped-transcript', None, known_tools=HOST)
            self.assertEqual(n, 2); self.assertEqual(by(rows)['contrasting_cases']['status'], 'warn'); self.assertEqual(len(missing), 2)
            for c in missing: s.record_case('timestamped-transcript', 2, c, walk, 'works')
            n, rows, missing = s.check('timestamped-transcript', 2, known_tools=HOST)
            self.assertEqual(by(rows)['contrasting_cases']['status'], 'pass')

    def test_bad_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s = core.Drafts(Path(d))
            for bad in ('../x', 'A', 'a b', ''): self.assertRaises(ValueError, s.save, bad, GOOD)
            self.assertRaises(ValueError, s.save, 'abc', '  ')
            s.save('abc', GOOD)
            self.assertRaises(ValueError, s.record_case, 'abc', 1, 'nope', 'x' * 100, 'works')
            self.assertRaises(ValueError, s.record_case, 'abc', 1, 'limited-offline', 'short', 'works')
            self.assertRaises(ValueError, s.record_case, 'abc', 1, 'limited-offline', 'x' * 100, 'great')
            self.assertRaises(ValueError, s.get, 'abc', 9)
            self.assertRaises(ValueError, s.get, 'zzz')

    def test_install_needs_clean_checks_and_cases_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            root_ = Path(d); s = core.Drafts(root_ / 'drafts'); skills = root_ / 'skills'
            s.save('timestamped-transcript', BAD)
            with self.assertRaisesRegex(ValueError, 'failing checks'): s.install('timestamped-transcript', 1, skills)
            s.save('timestamped-transcript', GOOD)
            with self.assertRaisesRegex(ValueError, 'cases missing'): s.install('timestamped-transcript', 2, skills)
            self.assertFalse(skills.exists())
            for c in core.CASES: s.record_case('timestamped-transcript', 2, c, 'x' * 100, 'works')
            out = s.install('timestamped-transcript', 2, skills)
            self.assertEqual((skills / 'timestamped-transcript/SKILL.md').read_text(), GOOD); self.assertEqual(out['revision'], 2)
            with self.assertRaisesRegex(ValueError, 'already exists'): s.install('timestamped-transcript', 2, skills)


class ResourceTests(unittest.TestCase):
    def test_resources_are_bounded_names_and_facts(self):
        out = core.resources(True, ['python3', 'definitely-not-installed', '../bad'])
        self.assertIn('cpu_count', out); self.assertIn('python3', out['executables']); self.assertFalse(out['executables']['definitely-not-installed']['found'])
        self.assertNotIn('../bad', out['executables'])
        self.assertIn('not probed', out['executables']['definitely-not-installed']['version'])
        self.assertLessEqual(len(out['cached_models']), 60); self.assertIn('No model was loaded', out['notice'])
        self.assertLess(len(json.dumps(out)), 40000)
        self.assertNotIn('cached_models', core.resources(False))


class RegistrationTests(unittest.TestCase):
    def test_registration_hook_and_handlers(self):
        ctx = Ctx(); module.register(ctx)
        self.assertEqual(set(ctx.tools), set(module.TOOLS)); self.assertTrue(ctx.skills['first-principles-skill-builder'].is_file())
        self.assertEqual(module.on_pre_tool_call('skillbuilder_install')['action'], 'approve')
        self.assertIsNone(module.on_pre_tool_call('skillbuilder_save'))
        out = json.loads(ctx.tools['skillbuilder_check']['handler']({'text': BAD}))
        self.assertFalse(out['ok']); self.assertIn('personal_paths', out['failing'])
        self.assertIn('error', json.loads(ctx.tools['skillbuilder_install']['handler']({'name': 'nope-nope'})))
        for t in ctx.tools.values(): self.assertFalse(t['schema']['parameters']['additionalProperties'])

    def test_end_to_end_through_handlers(self):
        with tempfile.TemporaryDirectory() as d:
            store = core.Drafts(Path(d) / 'drafts'); module._store = lambda: store
            ctx = Ctx(); module.register(ctx); h = lambda n, a: json.loads(ctx.tools[n]['handler'](a))
            self.assertEqual(h('skillbuilder_save', {'name': 'timestamped-transcript', 'text': BAD})['revision'], 1)
            c1 = h('skillbuilder_check', {'name': 'timestamped-transcript'}); self.assertFalse(c1['ok']); self.assertFalse(c1['ready_to_install'])
            self.assertEqual(h('skillbuilder_save', {'name': 'timestamped-transcript', 'text': GOOD, 'note': 'fixed'})['revision'], 2)
            for c in core.CASES: r = h('skillbuilder_case', {'name': 'timestamped-transcript', 'case': c, 'walkthrough': 'x' * 100, 'verdict': 'works'})
            self.assertEqual((r['revision'], r['cases_missing']), (2, []))
            c2 = h('skillbuilder_check', {'name': 'timestamped-transcript'}); self.assertTrue(c2['ok']); self.assertEqual(c2['cases_missing'], [])
            self.assertIn('error', h('skillbuilder_case', {'name': 'timestamped-transcript', 'case': 'bogus', 'walkthrough': 'x' * 100, 'verdict': 'works'}))


class LiveRunFindings(unittest.TestCase):
    """Defects found in the first live Hermes run (2026-11-10)."""

    def test_passing_rows_do_not_repeat_the_requirement(self):
        r = by(core.lint(GOOD, known_tools=HOST))
        for c in ('acceptance', 'degraded_mode', 'size'):
            self.assertEqual(r[c]['status'], 'pass'); self.assertNotIn('needs', r[c]['detail']); self.assertNotIn('keep 200', r[c]['detail'])

    def test_check_without_name_or_text_is_a_clear_error(self):
        ctx = Ctx(); module.register(ctx); out = json.loads(ctx.tools['skillbuilder_check']['handler']({}))
        self.assertIn('give the draft name', out['error'])

    def test_resources_do_not_name_hardware_or_home_user(self):
        r = core.resources(False); self.assertNotIn('cpu_model', r)
        self.assertEqual(core._scrub('git at /home/alice/bin/git 1.0'), 'git at /home/<user>/bin/git 1.0')
        for g in r['gpus'] or []: self.assertEqual(set(g), {'vendor', 'vram_gb'})


if __name__ == '__main__': unittest.main()
