---
name: first-principles-skill-builder
description: Create, check or improve an agent skill so it adapts a concrete workflow to the tools, models, hardware, subscriptions, budget and privacy limits that actually exist. Use when asked to write a skill, review a skill for portability, or fix a skill that only works on one machine; not for ordinary writing or coding.
---

# First Principles Skill Builder

This skill turns a goal into an executable decision process: how to reach the goal
with resources that exist, or what exact capability is missing. It is not a
transcript of how one machine solved the task. Use it when a skill is being written,
audited for portability, or revised after it failed on someone else's setup.

Read the [bundled wiki](../../llmwiki/first-principles-skill-builder/index.md) once. It has the resource decisions,
a worked example and failure diagnosis. Load only the page you need.

Helper tools (all deterministic, none calls a model): `skillbuilder_resources`,
`skillbuilder_save`, `skillbuilder_check`, `skillbuilder_case`, `skillbuilder_install`.
The reasoning, the writing and the judgment are yours; the tools only gather facts,
lint structure, and keep revisions and evidence.

## 1. Establish the goal and evidence

Read the request, project instructions and any existing implementation. Record the
intended result, acceptance checks, inputs and which side effects are authorized.
Separate requirements from examples and preferences: an audio recognizer needs
timestamps; it does not need a particular vendor or runtime. Keep explicitly
requested choices, accepted work and pauses.

Do not interview when the answer is already known. Ask what is missing, in ordinary
chat: output, language and quality; hardware; offline or upload permission; which
subscriptions or API access exist; budget and acceptable waiting time. An app
subscription is not proof of API access or unlimited allowance, so ask about local
and remote resources separately, any claimed API credit and its expiry, and the
maximum extra spend per job and per month (zero is valid). Save confirmed non-secret
choices with the task so the questions are not repeated. A saved budget is not an
enforceable cap and not permission to spend.

## 2. Discover before recommending

Call `skillbuilder_resources` and read what the host exposes (its tools, skills,
connected capabilities). It reports executables with versions, CPU, RAM, free disk,
NVIDIA GPU and cached model names without loading a model or reading credentials.
Reuse unchanged results. Distinguish four levels: documented, available, configured,
tested. Only tested counts as working.

Recommend a few viable paths from what was found. Prefer free and local options that
meet the need, and state quality, memory, latency, download, transfer and recurring
cost tradeoffs. Check changeable provider claims against the provider's own
documentation. Do not silently pick a hosted service, paid model, local replacement
or new runtime when the choice matters to the user. Do not scan account stores for
subscriptions.

## 3. Write the adaptive workflow

For each essential capability in the skill, write:

- the required behavior and input/output contract, with units and provenance;
- how to discover and test a compatible tool or backend in the current environment;
- the smallest setup or composition needed if it is missing;
- which choice or authorization is still needed before a consequential action;
- acceptance evidence, bounded failure handling and an honest degraded mode.

Keep task logic independent of provider and transport. Put vendor-specific detail in
optional references loaded after a choice is made. Do not pretend incompatible tools
share semantics: text-only speech recognition cannot supply word timing; a text
model cannot inspect an image it never saw. Keep uncertainty instead of inventing
intermediate data or success.

A skill may assemble scripts, configuration and existing tools to close a real gap.
Make that setup concrete and reviewable, do authorized reversible preparation, and
ask only for the remaining approval. Never give the generated skill broad permission
to install software, download large models, spend money, upload private inputs,
publish or change live systems.

Reason inside the active harness. Specialist models serve a selected task through the
selected interface; they are not renamed agent workers. If a required interface is
missing, say so as a blocker. Do not bypass protections or swap in another provider
unasked.

## 4. Make it useful, then test it

Use a precise name and description (what task, what trigger). Put in only
instructions that change behavior. Avoid generic wrappers (a "write a skill",
"scaffold" or "find skills" skill is not a purpose) and boilerplate files. Reuse any
skill validator the host offers; test any script you add.

Loop until `skillbuilder_check` has no failures:

1. `skillbuilder_save` the draft (every save is a new revision).
2. `skillbuilder_check` it; fix each failing check from its offending line.
3. Walk the draft through the three contrasting cases and record each with
   `skillbuilder_case`: `limited-offline` (limited CPU, offline, no subscription),
   `capable-gpu-cached` (capable GPU, cached models), `hosted-selected` (a hosted
   service the user explicitly chose). Say which path the skill takes, what it needs
   and what the result is. A missing optional backend must leave the other paths
   usable. A missing essential capability must produce a specific setup choice or
   blocker, never placeholder success. Revising the text means recording the cases
   again for the new revision.
4. Warnings are judgment calls: fix them or state why they are fine.

Exercise only capabilities and side effects authorized for the test. A lint or a
mocked check is not a live quality review; say which parts were never run.

## 5. Finish

Report the skill's location, the checks actually run, resource choices and open
limits. Keep automatic discovery on unless the user asks for manual-only use.
Installing is separate: `skillbuilder_install` scans the draft for prompt injection,
asks a person to confirm, refuses failing checks, missing cases and overwrites. If the
scan refuses with findings, show each one (file and line) and fix the draft; pass
`allow_findings` only when the user has read them and says to install anyway. Permission to make a local skill is
not permission to publish or distribute private sources.

## Acceptance for this skill's own work

Done when: the final revision passes `skillbuilder_check` (or each remaining warning
is explained), all three cases are recorded for that revision with honest verdicts
(`blocked` is a valid verdict), and the report lists what was and was not run.

## Plugins that ship knowledge

A plugin skill should ship a self-contained `llmwiki` with domain knowledge, actual
tool contracts, failure lessons, provenance and evidence status. Link a short index
from the skill, load details progressively, copy no private account, device or
credential data, and remember that knowledge does not prove a backend is installed
or authorized. An index plus copied tool names is not enough: include concrete
resource decisions, a worked flow, failure diagnosis and observable acceptance.
