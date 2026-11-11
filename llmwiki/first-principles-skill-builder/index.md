---
status: SOURCE-REVIEWED
curated: 2026-11-10
---
# first-principles-skill-builder LLM wiki

Read this index on first use, then only the page you need. The wiki ships inside
this plugin and equips the active host model; it is not a separate LLM service and
it does not install or authorize any backend.

## What the plugin is for

Building, checking and improving agent skills so that each one reaches its goal with
the tools, models, hardware, subscriptions and permissions that actually exist, and
says precisely what is missing when it cannot. The decision process lives in the
registered skill. Five deterministic helpers close real gaps: facts about this
machine, a per-check lint of a draft, stored walk-throughs of three contrasting
cases, numbered draft revisions, and an approval-gated install.

It is not a generic "write a skill" wrapper, a scaffold generator or a skill finder.
Those workflows are retired, and the lint refuses drafts that depend on them.

## Knowledge map

- [Task guide](task-guide.md): setup decisions, the loop, a worked end-to-end example
  (a timestamped-transcript skill built and improved), acceptance criteria.
- [Resource decisions](resource-decisions.md): how to turn discovered resources into
  a few recommended paths; what each level of evidence means.
- [Failure diagnosis](failure-diagnosis.md): each check, why it fires, how to fix it,
  and the ways the helpers themselves can mislead.
- [Actual tool contracts](tools.md) and [registration schemas](contracts.json).
- [README](../../README.md);
  [verification record](../../VERIFICATION.md); [manifest](../../plugin.yaml).

## Rules that apply everywhere

- Reasoning belongs to the host agent. No helper calls a model or an agent.
- Ask only for what is missing, in ordinary chat. Do not make the person dictate ids,
  numbers or every choice; discover, diagnose and correct first.
- A structural lint is not a quality review. Say which paths were never run.
- Local, reversible preparation is fine. Installs, downloads, uploads, spending and
  publication need their own explicit approval.
- Keep private paths, accounts, device ids and credentials out of drafts and wiki.
