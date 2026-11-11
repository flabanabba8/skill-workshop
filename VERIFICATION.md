# Verification

## Skill Workshop 0.1.0 (the suite)

- **Tests:** the three parts' own offline tests, adapted to load the whole suite as one plugin, plus a suite test. From the plugin folder they run with `python -m unittest discover -s tests -t .`: 60 tests pass (21 Skill Miner, 16 Skill Builder, 15 Taint Shield, 8 suite), also with ResourceWarning as an error (unittest is the supported runner; pytest collection is not set up). The suite test checks that `register()` exposes exactly the 14 tools and the hooks declared in `plugin.yaml`, once each, with nothing else registered; that each part's skill file exists; that the tool reference in `llmwiki/tools.md` lists exactly the registered tools; that every link in the wiki and the skills resolves; that the two install tools still ask for approval; and that each part gets its own folder under one suite data folder.
- **Hermes admission:** `hermes plugins validate <clean export of the commit> --install-deps` with Hermes v0.23.0 in a disposable Hermes home: all checks passed (manifest, `requires_hermes`, loadable, no Python dependencies, the capability probe matched the declared tools and hooks, no built-in tool collisions, security scan safe, no core override) with no warnings. The only extra line is the informational `Isolation - runs in the plugin host`.
- **Workflow preflight and secret/identity audit:** both clean on the tree and the history before release.
- **What the suite changes from the stand-alone plugins:** the parts are copied in as sub-packages with their behaviour unchanged. Three things differ: data folders are now sub-folders of `plugin-data/skill-workshop/` (data from the stand-alone plugins is not migrated); the skill and wiki files moved under the suite's `skills/` and `llmwiki/`; Taint Shield's hook is registered before the two install-approval hooks. The parts' provenance hash lists were dropped because they described the old file layout.

## Live evidence belongs to the parts

The live runs and the demonstrations of each part were made with the stand-alone plugins, not with this bundle. They are described in each part's own record, kept below in short form. Nothing here claims a live run of the bundled plugin.

### Skill Miner (stand-alone 0.2.1)
- 21 offline tests on synthetic session databases: repeated-workflow detection, held-out replay, redaction, diagnose size and redaction, refine keeps the original bytes, check per item, gated install, retired-workflow refusal, human skill names.
- A read-only scan of the author's real 90-day history (72 sessions with tool calls) found 6 candidate patterns and recommended none.
- Not live (per its own record): no real history was mined by a live host agent and no revision was installed; a larger or more repetitive history, a real proposal reviewed and used by a person, and Windows are unverified.

### First Principles Skill Builder (stand-alone 0.1.0)
- 16 offline tests cover every helper, the lint on a deliberately bad and an improved draft, revisions, cases, install gating, bounded resource output and registration.
- A real Hermes session built a skill for turning meeting recordings into searchable notes: revision 1 failed the degraded-mode check, revision 2 passed; three contrasting cases were recorded; nothing was installed. Defects found there were fixed in source.
- Not verified: the install approval prompt on screen, other platforms, AMD/Intel/Apple GPUs, and whether built skills perform well (the checks are structure, not quality).

### Taint Shield (stand-alone 0.2.2)
- 15 offline tests, including a small hand-written corpus of 9 injected pages with the actions they try to cause (all must be stopped) and 7 ordinary agent flows (all must be left alone). The corpus is written by the plugin author and is not an independent benchmark.
- Through Hermes's real tool path in a throwaway home: an injected page was recorded by the real `post_tool_call` hook, the real terminal call for an exfiltration command was blocked and never ran, and a normal `echo` ran.
- Live demo runs found and fixed: a copy of a secret-named file after an injected phrase was not stopped; the file reader's JSON output hid command lines from the detector.
- Not verified: a live agent session with a real model reading a real hostile page beyond those demo runs, rephrased or encoded injections, the false-positive rate on long real sessions, Windows.

## Not verified for the suite

- Running the bundled plugin in a live Hermes session with all three parts enabled together (for example how the Shield and the install approvals interact in the on-screen prompt).
- Platforms other than Linux.
