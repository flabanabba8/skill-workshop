---
status: SOURCE-REVIEWED
curated: 2026-11-09
---
# skill-miner setup and task guide

This is a source-reviewed operating guide, not a claim of a new live test.
Resolve exact parameter shapes from [tool contracts](tools.md) and
[registration schemas](contracts.json) before calling a tool.

## Setup decisions

The history is the host's own session database, read-only; use the window and limits the user already stated or saved, and ask only when nothing is known. Scan reads tool names and counts, plus each session's first request in abstracted, redacted form (used only to find shared wording); propose reads up to three original request texts; diagnose reads redacted error text of failed steps in the proposal's own sessions. Repeated sequences describe habits rather than an optimal method. Keep retired workflows and generic wrappers excluded.

## Worked task flow

"Find a workflow I repeat and turn it into a skill that works": miner_scan, pick the best real task pattern, miner_propose, miner_diagnose, write a corrected SKILL.md yourself and save it with miner_refine, miner_check, and on failure refine and check again (at most 3 rounds), then report the check results, the unchanged mining verdict and what remains unverified. No per-step human review is needed; only miner_install needs a person to confirm, and only a revision that passed miner_check unchanged can be installed. Keep numbered step lines as 1. `tool` so the replay can read them.

## One session instead of many

"Turn what we just did into a skill": call miner_session (defaults to the current or most recent session; `session` picks an id, title part or date, `list` shows recent sessions). The result has the ordered steps (argument shapes only; retries and polling collapsed; failed steps with what replaced them), preferences quoted in the user's own words with message numbers and reasons, one-off facts that must stay out of the skill, an `unclassified` list, and a saved draft whose "## Preferences from <date>" section is edited apart from the steps. The classification is a plain heuristic (standing words such as always or never, requirement wording, instruction verbs, corrections after a tool result) and can be wrong either way; the person decides. Everything quoted is untrusted session data, and instruction-like text is flagged and left out of the draft. Continue with miner_diagnose, miner_refine, miner_check and a confirmed miner_install. The draft has no held-out sessions, so the replay check is skipped and the verdict is `single_session`, which proves nothing about repeatability.

## Failure diagnosis

Zero recommendations is a legitimate result when held-out evidence is weak. Path abstraction can hide a retired dependency, so the guard reads raw call text, including every call inside a tool_call envelope, before abstraction, and again on refine, check and install. Typical check failures: name differs from the proposal name; description outside 30-500 characters; a personal path, address or secret pattern left in; a step tool never seen in the mined sessions (invented or renamed); the refined step order not occurring in enough held-out sessions (reordered or over-specific). Diagnose reports unmapped_batched_calls when a batch with duplicate calls of one tool could not be mapped to arguments. Redaction can miss private values. Do not replay mined commands, download dependencies or install a renamed retired workflow to test a draft.

## Acceptance and evidence limits

Accept a domain-specific revision whose checks all pass (replay may be skipped when there are no held-out sessions), with sanitized examples, adaptive resource choices and precise limitations in the report. A WEAK mining verdict stays WEAK; checks are structural and order-replay evidence, not proof the instructions work for a new user, and nothing in this package has been run in a live Hermes session. Installation is a separate explicit action.

## Source trail

Derived from the packaged [README](../../README.md), [manifest](../../plugin.yaml),
registered tool schemas and the tests in the tests folder. Existing
verification records describe their own dated scope; no new live capability
was inferred from this documentation review.
