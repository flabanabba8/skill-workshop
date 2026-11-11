"""Loads the whole suite once, as Hermes does (a package with sub-packages)."""
import importlib.util
from pathlib import Path
import sys

root = Path(__file__).parents[1]
NAME = 'skill_workshop_fixture'
if NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(NAME, root / '__init__.py', submodule_search_locations=[str(root)])
    suite = importlib.util.module_from_spec(spec); sys.modules[NAME] = suite; spec.loader.exec_module(suite)
suite = sys.modules[NAME]
