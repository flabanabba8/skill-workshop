"""Tests. hermes_state is imported first: other test modules replace parts of hermes_cli temporarily, and the miner tests need the real session store."""
import hermes_state  # noqa: F401
