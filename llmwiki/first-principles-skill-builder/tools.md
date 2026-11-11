# Actual tool contracts

Registered source schemas; registration alone does not establish that any helper was run live in a Hermes session.
Every tool is deterministic and offline; none calls a model.

## skillbuilder_resources

Report this machine's CPU, RAM, free disk, GPU (NVIDIA via nvidia-smi), common executables with versions, cached model names, and the host's registered tools and skills. Names only: loads no model, reads no credentials.

Inputs: `include_model_cache` (optional), `extra_executables` (optional).

## skillbuilder_save

Save a draft SKILL.md as a new numbered revision under the plugin data folder. Never overwrites an earlier revision and installs nothing.

Inputs: `name` (required), `text` (required), `note` (optional).

## skillbuilder_check

Check a saved draft revision (or unsaved text) and report each check separately with offending lines: frontmatter, description quality, size, personal paths, provider ids, acceptance, degraded mode, retired workflows, harness neutrality, side effects, referenced files and tools, and recorded contrasting cases.

Inputs: `name` (optional), `revision` (optional), `text` (optional), `base_dir` (optional).

## skillbuilder_case

Record your walk-through of one contrasting case for a draft revision: limited-offline, capable-gpu-cached or hosted-selected. Returns which cases are still missing.

Inputs: `name` (required), `revision` (optional), `case` (required, one of limited-offline/capable-gpu-cached/hosted-selected), `walkthrough` (required), `verdict` (required, one of works/degraded/blocked).

## skillbuilder_install

Install a checked draft revision as a skill. Refuses failing checks, missing contrasting cases and overwrites, and always requires a person to confirm.

Inputs: `name` (required), `revision` (optional).

