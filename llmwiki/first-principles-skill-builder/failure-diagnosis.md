---
status: SOURCE-REVIEWED
curated: 2026-11-10
---
# Failure diagnosis

Each `skillbuilder_check` row has a status (`pass`, `fail`, `warn`, `skipped`) and,
when relevant, the offending lines. Fix at the line, not by rewording around the
pattern.

| Check | Fires when | Fix |
| --- | --- | --- |
| frontmatter | no closing `---`, bad name slug, no description, name differs from the saved draft name | Use `name: lowercase-hyphen` and a description; keep the name equal to the draft name |
| description_quality | under 40 or over 1024 chars, no "use when/for/to" trigger, mostly generic words, retired wrapper name | Name the concrete task and the situation that should trigger it |
| size | over 500 lines (fail), over 300 or tiny body (warn) | Move vendor detail to a reference loaded after a choice; give a tiny body real decisions |
| personal_paths | `/home/<user>`, `/Users/<user>`, `C:\Users\...` | Say how to discover the location or take it as an input |
| provider_ids | model or provider id on a line that says must/only/always/required (fail); any id otherwise (warn) | Make it an example chosen after discovery ("for example"), or describe the capability needed |
| acceptance | none of acceptance/verify/done when/observable in the body | State a check a run can fail |
| degraded_mode | no degraded/fallback/blocker/setup-choice wording | State what happens when the essential capability is missing |
| retired_workflows | references to retired helper skills or scripts, or a retired name | Remove the dependency; use native tools in the main session |
| harness_neutral | names such as agents/openai.yaml, AGENTS.md, CLAUDE.md | Describe what the file does so another harness can follow |
| side_effects | install/download/upload/publish words and no approval wording anywhere | Add the approval step and who gives it |
| referenced_files | a link or `dir/file.ext` that does not exist under `base_dir` (`skipped` without it) | Create the file, inline it, or drop the reference |
| referenced_tools | snake_case names in backticks not in the host registry (`skipped` if unreachable) | Confirm the tool exists, or say how to discover it. Plain function or variable names in code spans can false-alarm; judge, then explain |
| contrasting_cases | fewer than three cases recorded for this revision | Walk and record the missing ones |

## Ways the helpers can mislead

- Heuristics are regexes. A line can pass while being wrong (a hedge word can excuse
  a mandatory model id) or fail while being right. Read the line.
- The lint cannot see whether instructions work. Only a real run can.
- `skillbuilder_case` stores the agent's reasoning. Do not record `works` for a path
  you did not reason through, and do not claim it was executed.
- Cases belong to a revision. After editing, the new revision shows them missing.
  That is intended.
- `host_tools: null` or `referenced_tools: skipped` mean the host registry was out
  of reach; do not treat tool names as verified.
- `skillbuilder_install` refuses overwrites. To replace a skill, the person removes
  or renames the old one; the helper will not.

## Errors from the tools

- `name must be lowercase letters, digits and hyphens`: fix the name.
- `Draft X has revisions [..], not N`: use a listed revision or omit it for the latest.
- `walkthrough must say ... 80+ characters`: describe the path, needs and result.
- `Refusing to install: failing checks [...]` / `contrasting cases missing [...]`:
  fix and re-record; there is no override.
