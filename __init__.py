"""Skill Workshop: Skill Miner, First Principles Skill Builder, Taint Shield and Skill Guard in one plugin.

Each part is a sub-package that registers exactly what its stand-alone plugin registered.
The shield goes first so its hook sees a tool call before the parts' install approvals.
"""
from . import builder, guard, miner, shield, storage

PARTS = (shield, guard, miner, builder)


def register(ctx):
    for part in PARTS:
        part.register(ctx)
