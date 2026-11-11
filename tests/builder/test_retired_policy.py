"""Policy fixtures: drafts that depend on retired workflows must fail the check and never install. Nothing here invokes a worker."""
from pathlib import Path
import tempfile
import unittest
from tests.builder.test_builder import core, BAD, GOOD, HOST, by


class RetirementTests(unittest.TestCase):
    def test_retired_dependency_fails_with_its_line(self):
        text = BAD + 'Load the skill with load_skill("write-a-skill") if stuck.\n'  # retirement-policy
        r = by(core.lint(text, known_tools=HOST))['retired_workflows']
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['lines'][0]['line'], 12)

    def test_retired_wrapper_name_fails_and_cannot_install(self):
        name = 'write-a-skill'  # retirement-policy
        r = by(core.lint(GOOD.replace('timestamped-transcript', name), known_tools=HOST))
        self.assertEqual(r['retired_workflows']['status'], 'fail'); self.assertEqual(r['description_quality']['status'], 'fail')
        with tempfile.TemporaryDirectory() as d:
            s = core.Drafts(Path(d) / 'drafts'); s.save(name, GOOD.replace('timestamped-transcript', name))
            for c in core.CASES: s.record_case(name, 1, c, 'x' * 100, 'works')
            with self.assertRaisesRegex(ValueError, 'failing checks'): s.install(name, 1, Path(d) / 'skills')
            self.assertFalse((Path(d) / 'skills').exists())


if __name__ == '__main__': unittest.main()
