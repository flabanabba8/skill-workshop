---
status: SOURCE-REVIEWED
curated: 2026-11-10
---
# Resource decisions

## Evidence levels

- **documented**: a vendor page or README says it exists. Verify changeable claims
  (pricing, quotas, availability) against the primary source before relying on them.
- **available**: the executable, package, model file or host tool is present
  (`skillbuilder_resources` shows this).
- **configured**: credentials/paths/settings are in place. The helper never reads
  credentials, so it cannot tell you this; ask the person or test the interface.
- **tested**: a bounded call with a tiny input produced the right kind of result.

Only tested is "works". Report the level for every choice.

## Reading the resources report

- `gpus: null` means nvidia-smi found nothing. AMD, Intel or Apple accelerators are
  not detected; ask or inspect with the host's own tools before assuming CPU only.
- `ram_available_gb` matters more than `ram_gb` for loading a model.
- `cached_models` are directory names only; presence is not proof the files are
  complete or that a runtime can load them.
- `host_tools` and `host_skills` show what the host already offers. Prefer composing
  those over building a new script. `null` means the registry was not reachable
  from the helper, not that the host has none.
- Versions come from `--version` of a fixed list of executables. Names passed in
  `extra_executables` are only located, never run.

## From facts to a few paths

Offer two or three, cheapest and most private first:

1. **Local, no extra install**: what the machine can do with what is present. State
   speed and quality honestly (small model, long wait).
2. **Local with a one-time setup**: the smallest install or download that closes the
   gap, with size, time and reversibility. Needs approval before it runs.
3. **Hosted**: only as an option for the person to select. Before recommending,
   check: is API access separate from an app subscription, what does one job cost,
   what leaves the machine, and what spend cap applies (zero is valid)? A saved
   budget is not an enforced cap.

Never pick a hosted service, paid model, new runtime or large download silently.

## Capability semantics to keep apart

Plain-text recognition is not word timing. A text model cannot inspect an unseen
image. A translation tool is not a summarizer. A model "supporting" a feature in a
catalogue is not proof the chosen endpoint implements it. When two tools differ in
a way that changes the result, the skill must say which it needs.

## Saved answers

Store confirmed non-secret choices (output language, upload permission, spend limit)
with the task so they are not asked again. Never store credentials in a skill or
in the wiki.
