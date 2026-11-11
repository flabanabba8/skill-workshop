"""The suite registers exactly what plugin.yaml declares, and keeps each part's data apart."""
from pathlib import Path
import os
import re
import tempfile
import unittest

from tests.fixture_suite import suite, root


def declared(key):
    text = (root / 'plugin.yaml').read_text()
    block = re.search(r'^%s:\n((?:  - .*\n?)+)' % key, text, re.M).group(1)
    return [line[4:].strip() for line in block.splitlines()]


class Ctx:
    def __init__(self): self.tools = []; self.hooks = []; self.skills = {}; self.other = []
    def register_tool(self, **kw): self.tools.append(kw['name'])
    def register_hook(self, name, fn, **kw): self.hooks.append(name)
    def register_skill(self, name, path, description=''): self.skills[name] = Path(path)
    def __getattr__(self, name):
        if name.startswith('register_'):
            return lambda *a, **k: self.other.append(name)
        raise AttributeError(name)


class SuiteRegistration(unittest.TestCase):
    def setUp(self): self.ctx = Ctx(); suite.register(self.ctx)

    def test_tools_are_exactly_the_declared_tools_once_each(self):
        self.assertEqual(sorted(self.ctx.tools), sorted(declared('provides_tools')))
        self.assertEqual(len(self.ctx.tools), len(set(self.ctx.tools)))
        self.assertEqual(len(self.ctx.tools), 14)

    def test_hooks_are_exactly_the_declared_hooks(self):
        self.assertEqual(sorted(set(self.ctx.hooks)), sorted(declared('provides_hooks')))
        self.assertEqual(sorted(self.ctx.hooks), sorted(['pre_llm_call', 'post_tool_call', 'transform_tool_result', 'pre_tool_call', 'pre_tool_call', 'pre_tool_call']))

    def test_nothing_else_is_registered(self):
        self.assertEqual(self.ctx.other, [])

    def test_each_part_skill_is_registered_and_exists(self):
        self.assertEqual(sorted(self.ctx.skills), ['first-principles-skill-builder', 'skill-miner', 'taint-shield'])
        for path in self.ctx.skills.values(): self.assertTrue(path.is_file(), path)

    def test_tool_reference_lists_exactly_the_registered_tools(self):
        text = (root / 'llmwiki/tools.md').read_text()
        listed = re.findall(r'^## (\w+)$', text, re.M)
        self.assertEqual(sorted(listed), sorted(self.ctx.tools))
        for part in ('skill-miner', 'first-principles-skill-builder', 'taint-shield'):
            part_text = (root / 'llmwiki' / part / 'tools.md').read_text()
            for name in re.findall(r'^## (\w+)$', part_text, re.M): self.assertIn(name, self.ctx.tools)

    def test_every_wiki_link_resolves(self):
        for md in list((root / 'llmwiki').rglob('*.md')) + list((root / 'skills').rglob('SKILL.md')):
            for target in re.findall(r'\]\(([^)#:]+)(?:#[^)]*)?\)', md.read_text()):
                self.assertTrue((md.parent / target).exists(), f'{md.relative_to(root)} -> {target}')

    def test_install_tools_still_need_approval_and_share_no_data_folder(self):
        self.assertEqual(suite.miner.on_pre_tool_call(tool_name='miner_install')['action'], 'approve')
        self.assertEqual(suite.builder.on_pre_tool_call('skillbuilder_install')['action'], 'approve')
        self.assertIsNone(suite.miner.on_pre_tool_call(tool_name='miner_scan'))
        self.assertIsNone(suite.builder.on_pre_tool_call('skillbuilder_save'))

    def test_each_part_gets_its_own_folder_under_one_suite_folder(self):
        import sys, types
        with tempfile.TemporaryDirectory() as home:
            storage = types.ModuleType('plugins.plugin_storage')
            def plugin_data_dir(name):
                d = Path(home) / 'plugin-data' / name; d.mkdir(parents=True, exist_ok=True); return d
            storage.plugin_data_dir = plugin_data_dir
            saved = {k: sys.modules.get(k) for k in ('plugins', 'plugins.plugin_storage')}
            sys.modules['plugins'] = sys.modules.get('plugins') or types.ModuleType('plugins'); sys.modules['plugins.plugin_storage'] = storage
            try:
                dirs = [suite.storage.part_data_dir(p) for p in ('skill-miner', 'first-principles-skill-builder', 'taint-shield')]
            finally:
                for k, v in saved.items():
                    if v is None: sys.modules.pop(k, None)
                    else: sys.modules[k] = v
            self.assertEqual({d.parent.name for d in dirs}, {'skill-workshop'})
            self.assertEqual(len({d.name for d in dirs}), 3)


if __name__ == '__main__': unittest.main()
