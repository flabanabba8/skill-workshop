"""Skill Workshop: Skill Miner, First Principles Skill Builder and Taint Shield in one plugin.

Each part is a sub-package that registers exactly what its stand-alone plugin registered.
The shield goes first so its hook sees a tool call before the parts' install approvals.
"""
from . import builder, miner, shield, storage

PARTS = (shield, miner, builder)


def register(ctx):
    for part in PARTS:
        part.register(ctx)
