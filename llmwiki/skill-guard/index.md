---
status: SOURCE-DERIVED
curated: 2026-11-11
---
# Skill Guard

Scans every skill before it is installed or used, including skills from other people.

- Install time: when Hermes writes a skill through `skill_manage`, or writes a file inside the skills folder, the new text is scanned first; findings are shown in an approval box. A skill added any other way (`hermes skills install`, copying a folder) is scanned the moment Hermes reports it landed.
- Use time: when a skill is loaded, its text is scanned. A flagged version nobody has approved is replaced by a warning; tell the user once, in plain words, and wait for their decision.
- Decisions are remembered by a hash of the skill's files: `clean`, `approved`, `quarantined` (flagged and waiting is `flagged`). Any change to any file is scanned again.
- Tools: [tools.md](tools.md).
- Heuristic, not proof: it finds hidden text, commands that send secrets out and instruction-override phrases, not every possible attack.

[Suite index](../index.md)
