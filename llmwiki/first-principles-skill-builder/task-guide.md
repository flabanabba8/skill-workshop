---
status: SOURCE-REVIEWED
curated: 2026-11-10
---
# Task guide

This is a source-reviewed operating guide. The helper behaviour described here was
exercised only by offline unit tests (see [verification](../../VERIFICATION.md)). Exact
argument shapes are in [tools](tools.md).

## Setup decisions

1. **Goal and acceptance first.** Write down the result the skill must produce, how
   a run proves it, the inputs, and which side effects are authorized. If the
   request or project files already say, do not ask again.
2. **Is a skill the right thing?** If the workflow will not repeat, or a single
   existing tool already does it, say so instead of building one.
3. **Resources.** Call `skillbuilder_resources`. Read its executables, GPU, RAM,
   cached model names and the host's own tools and skills. Then read
   [resource decisions](resource-decisions.md).
4. **Ask only what discovery cannot answer**: quality bar, offline or upload
   permission, subscriptions and separately verified API access, spend limits (zero
   is valid), waiting time. Remember confirmed non-secret answers.

## The loop

1. Draft `SKILL.md` for the goal: lead with what it is for and when to use it, then
   per capability: contract, how to discover/test a backend, smallest setup,
   authorization needed, acceptance evidence, degraded mode.
2. `skillbuilder_save` it (new numbered revision; earlier ones are kept).
3. `skillbuilder_check` it. Fix every `fail` from its listed line. Decide each `warn`.
4. Walk the three contrasting cases and record each with `skillbuilder_case`
   (`limited-offline`, `capable-gpu-cached`, `hosted-selected`) with a verdict of
   `works`, `degraded` or `blocked`. If the walk-through exposes a hole, fix the
   draft, save a new revision, and record the cases again for it.
5. When the check has no failures and all three cases exist for that revision,
   report. Install only if the person wants the skill in their skills folder:
   `skillbuilder_install` asks them to confirm.

## Worked example: a timestamped-transcript skill

The person says: "I record talks. I want to cite what was said by time. Make a skill
for it." Nothing else is given.

**Discover.** `skillbuilder_resources` returns (abridged, illustrative values):

```text
cpu_count 8, ram_gb 15.6, gpus null, cached_models [],
executables: ffmpeg found; python3 found; pip found; ollama null; whisper-cli null
host_tools: [..., "read_file", "terminal", ...]
```

No GPU, no cached model, no recognizer. A recognizer with timestamps is the essential
capability and it is missing; ffmpeg exists. So the skill must (a) find a recognizer
at run time, (b) offer a concrete setup choice when none exists, (c) not claim
timestamps from a text-only recognizer.

**First draft (written fast, copied from how one machine did it).** Saved as revision
1; it is `tests/fixtures/bad.md` in the plugin. `skillbuilder_check` reports:

```text
description_quality  fail  no trigger; mostly generic words
personal_paths       fail  line 8: a home-directory interpreter and script path
provider_ids         fail  line 9: a model name presented as mandatory ("only")
acceptance           fail  nothing says how a run proves success
degraded_mode        fail  nothing says what happens without the recognizer
harness_neutral      warn  line 11: names a host-specific config file
side_effects         warn  installs and downloads with no approval step
referenced_tools     warn  `transcribe_everything` is not a registered tool
```

(A draft that loads a retired generic skill by name would also fail `retired_workflows`; that case is a separate policy test. `referenced_files` is `skipped` unless `base_dir` is given; pass it for drafts that
ship reference files.)

**Improve.** Each fix comes from facts, not from the lint alone: the paths become
"discover a recognizer that returns segment timestamps"; the model becomes "smallest
model that fits memory, a larger cached one if a GPU exists"; downloads become "a
separate choice to ask about, with size"; acceptance becomes measurable (last
segment ends within 2 s of the file duration, no unexplained gaps over 10 s, every
start < end); the missing-recognizer branch becomes a blocker with a setup choice.
Saved as revision 2 (`tests/fixtures/good.md`); `skillbuilder_check` shows no
failures or warnings.

**Contrasting cases for revision 2** (what the agent records, in its own words):

- `limited-offline`, verdict `degraded`: "ffmpeg present, no recognizer. Skill stops
  with a setup choice: a small local recognizer (size stated) or a hosted one the
  user must select. Offers plain text only if a text-only tool exists, and says it
  cannot be cited by time. No timestamps are invented."
- `capable-gpu-cached`, verdict `works`: "Finds a timestamp-capable recognizer and a
  larger cached model, uses the GPU, runs the acceptance check, reports model and
  device used. No download needed."
- `hosted-selected`, verdict `works`: "Only after the user selected a service,
  confirmed upload of the audio and a per-job spend limit. Same acceptance check on
  the returned segments."

`skillbuilder_check` now reports `cases_missing: []`, `ready_to_install: true`.
The report to the person names the skill, the checks run, the three verdicts and
what was not run: no real recording was transcribed, because the example has no
recognizer installed.

## Observable acceptance criteria

- The final revision has zero `fail` rows in `skillbuilder_check`, and each `warn`
  is fixed or explained in the report.
- `cases_missing` is empty for that same revision number, and verdicts are honest
  (a `blocked` verdict with a specific setup choice is acceptable; placeholder
  success is not).
- Earlier revisions still exist (`rev-0001`, `rev-0002`, ...) with the cases
  recorded next to the revision they judged.
- The skill's own text states its acceptance check and degraded mode in terms a run
  could verify.
- The report separates what was run (lint, walk-throughs) from what was not (a live
  run of the new skill).

## What this does not establish

A passing check proves structure and the presence of the required parts. It does not
show the new skill gives good results. Only running it on a real task, with the
resources it names, does. Walk-throughs are the agent's reasoning, not execution.
