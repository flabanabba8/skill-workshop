# Actual tool contracts

Registered source schemas; registration alone does not establish live behavior.

## miner_scan

Scan recent sessions (tool names and counts only) for tool workflows you repeat, and check each against sessions held out of the mining. Returns ranked patterns with support, held-out hits and consistency.

Inputs: `days` (optional), `min_support` (optional), `min_steps` (optional).

## miner_propose

Draft a skill for one scanned pattern, using abstracted examples and up to three of your original request texts (redacted). Saves a proposal; installs nothing.

Inputs: `pattern_id` (required).

## miner_diagnose

Return bounded, redacted diagnosis context for one proposal or revision: the unchanged mining verdict and numbers, structural problems in the draft, and where its supporting sessions hit errors or retries. Reads only that proposal's own sessions. For the host agent to reason over; installs and changes nothing.

Inputs: `proposal_id` (required), `revision` (optional).

## miner_refine

Save your revised SKILL.md text as a new numbered revision next to the original proposal, which is never modified. Rejects retired workflows. Nothing is installed.

Inputs: `proposal_id` (required), `skill_text` (required), `notes` (optional).

## miner_check

Run deterministic checks on a revision (default latest; 0 is the original) and store the result: frontmatter, retired policy, leaked values, tools seen in the mined sessions, and a replay of its step order on held-out sessions. Not a quality guarantee; a weak mining verdict stays weak.

Inputs: `proposal_id` (required), `revision` (optional).

## miner_install

Install a proposal as a skill (the latest revision if any exist, or the given one; 0 is the original). A revision must have passed miner_check unchanged. Refuses to overwrite an existing skill and always requires a person to confirm.

Inputs: `proposal_id` (required), `revision` (optional).

