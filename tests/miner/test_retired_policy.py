"""Offline fixtures for the retirement policy; none invokes a worker."""
from tests.miner.test_miner import core, make_db
from tests.miner.statedb import Store
import json
from pathlib import Path
import tempfile
import unittest

class RetirementTests(unittest.TestCase):
    def test_saved_or_renamed_retired_proposal_cannot_be_installed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); props = core.Proposals(root / 'proposals')
            # Explicit policy fixtures; not executable dependency calls.
            cases = [('disposable-vision', '# native-looking title'), ('workflow-old-image', 'python vision_inspect.py'), ('find-skills', 'anything')]  # retirement-policy
            for name, text in cases:
                pid = props.save(name, text, {})
                with self.assertRaisesRegex(ValueError, 'Retired agent workflow'): props.install(pid, root / 'skills')
            self.assertFalse((root / 'skills').exists())

    def test_raw_dependency_is_rejected_before_its_path_is_abstracted(self):
        command = 'python /tmp/disposable-vision/scripts/vision_inspect.py'  # retirement-policy
        self.assertNotIn('vision_inspect', core.abstract(command))
        sessions = [{'id': 's', 'steps': [{'token': 'terminal:python', 'tool': 'terminal', 'args': {'command': command}}]}]
        with self.assertRaisesRegex(ValueError, 'Retired agent workflow'):
            core.draft({'_support': ['s'], 'steps': ['terminal:python']}, sessions, '/not-opened.db')

class RefinementRetirementTests(unittest.TestCase):
    def test_nested_retired_command_in_a_tool_call_envelope_is_caught_before_abstraction(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / 'state.db'); make_db(db, wrapped=True); store = Store(db)
            for sid in ('s00', 's01', 's03'):
                cid = 'x' + sid; bad = 'python /tmp/disposable-vision/scripts/vision_inspect.py a.png'  # retirement-policy
                store.msg(sid, 'assistant', tool_calls=[{'id': cid, 'function': {'name': 'tool_call', 'arguments': json.dumps({'calls': [{'name': 'terminal', 'arguments': {'command': bad}}]})}}])
                store.msg(sid, 'tool', '{"exit_code": 0}', tool_name='terminal', call_id=cid)
            store.close(); sessions = core.load(db, 30)
            with self.assertRaisesRegex(ValueError, 'Retired agent workflow'): core.draft({'steps': ['terminal:python'], '_support': ['s00']}, sessions, db)

    def test_retired_text_is_refused_on_refine_and_fails_check(self):
        with tempfile.TemporaryDirectory() as d:
            props = core.Proposals(Path(d) / 'p'); pid = props.save('workflow-ok-name', '---\nname: workflow-ok-name\n---\n', {})
            with self.assertRaisesRegex(ValueError, 'Retired agent workflow'): props.refine(pid, 'run vision_inspect.py now')  # retirement-policy
            self.assertEqual(props.revisions(pid), [])
            text = '---\nname: workflow-ok-name\ndescription: Use when you need a long enough description to pass the length check.\n---\nrun disposable-vision\n'  # retirement-policy
            result = core.check('workflow-ok-name', text, {}, [], [])
            self.assertFalse(result['passed']); self.assertIs(next(c for c in result['checks'] if c['check'] == 'retired_policy')['ok'], False)

if __name__ == '__main__': unittest.main()
