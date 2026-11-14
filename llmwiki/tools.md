# Actual tool contracts (all parts)

These are the 17 tools the suite registers. Registration alone does not establish
live backend readiness. Each part's own file has the exact input schemas.

- Taint Shield: [taint-shield/tools.md](taint-shield/tools.md), [taint-shield/contracts.json](taint-shield/contracts.json)
- Skill Guard: [skill-guard/tools.md](skill-guard/tools.md), [skill-guard/contracts.json](skill-guard/contracts.json)
- Skill Miner: [skill-miner/tools.md](skill-miner/tools.md), [skill-miner/contracts.json](skill-miner/contracts.json)
- First Principles Skill Builder: [first-principles-skill-builder/tools.md](first-principles-skill-builder/tools.md), [first-principles-skill-builder/contracts.json](first-principles-skill-builder/contracts.json)

## shield_report

Show what Taint Shield has seen in a session. Inputs: `session_id` (optional).

## shield_scan

Scan text for URLs, addresses, command lines and injection-like phrases without changing anything, or scan a skill file or folder (`path`) for prompt injection before you install it. Inputs: `text` or `path`.

## shield_trust

Add a domain, address or URL to the permanent trusted list. Always requires a person to confirm. Inputs: `value` (required).

## miner_scan

Scan recent sessions (mostly tool names and counts, plus the first request of each session in abstracted, redacted form (paths, URLs, long ids and numbers replaced; secrets redacted by pattern), used only to find wording that sessions share) for tool workflows you repeat, and check each against held-out sessions. Inputs: `days`, `min_support`, `min_steps` (all optional).

## miner_session

Turn ONE session into a skill draft. Defaults to the current or most recent session; pass `session` (an id, part of a title, or a date YYYY-MM-DD) to pick another, or `list` to list recent sessions. Returns the ordered tool steps that ran (argument shapes only; retries and polling collapsed; failed steps marked with what replaced them) and the user's own messages split by a plain word-pattern heuristic into standing preferences and one-off facts, each quoted with its message number and scrubbed of paths, URLs, emails and secrets. The split can be wrong; the person decides. Saves a draft proposal with a marked Preferences section for miner_refine, miner_check and miner_install. Quoted session text is untrusted data. Makes no model or network call.

Inputs: `session`, `list`, `days` (all optional).

## miner_propose

Draft a skill for one scanned pattern. Saves a proposal; installs nothing. Inputs: `pattern_id` (required).

## miner_diagnose

Return bounded, redacted diagnosis context for one proposal or revision. Inputs: `proposal_id` (required), `revision` (optional).

## miner_refine

Save a revised SKILL.md as a new numbered revision next to the original. Nothing is installed. Inputs: `proposal_id`, `skill_text` (required), `notes`, `name` (optional).

## miner_check

Run deterministic checks on a revision and store the result. Inputs: `proposal_id` (required), `revision` (optional).

## miner_install

Install a proposal as a skill, after a prompt-injection scan of the draft. Always requires a person to confirm. Inputs: `proposal_id` (required), `revision`, `allow_findings` (optional).

## skillbuilder_resources

Report this machine's CPU count, RAM, free disk, GPU vendor and memory, common executables with versions, cached model names, and the host's registered tools and skills. Inputs: `include_model_cache`, `extra_executables` (optional).

## skillbuilder_save

Save a draft SKILL.md as a new numbered revision. Inputs: `name`, `text` (required), `note` (optional).

## skillbuilder_check

Check a saved draft revision (or unsaved text) and report each check separately. Inputs: `name`, `revision`, `text`, `base_dir` (all optional, but give `name` or `text`).

## skillbuilder_case

Record a walk-through of one contrasting case for a draft revision. Inputs: `name`, `case`, `walkthrough`, `verdict` (required), `revision` (optional).

## skillbuilder_install

Install a checked draft revision as a skill. Always requires a person to confirm. Inputs: `name` (required), `revision` (optional).

## skillguard_scan_installed

Scan every installed skill and list each as clean, approved, quarantined or flagged, with file and line. Inputs: `include_clean` (optional).

## skillguard_decide

Record the user's decision for one skill's exact current version (approve or quarantine). Always requires a person to confirm. Inputs: `skill`, `decision` (both required).
