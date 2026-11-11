"""Where each part of the suite keeps its data.

One Hermes data folder for the whole plugin (``plugin-data/skill-workshop/``) with one
sub-folder per part, so the parts never share files and stay stable if one is changed.
Data written by the stand-alone plugins (``plugin-data/skill-miner/`` and so on) is not
read or migrated.
"""
from pathlib import Path


def part_data_dir(part):
    from plugins.plugin_storage import plugin_data_dir
    root = plugin_data_dir('skill-workshop') / part
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return Path(root)
