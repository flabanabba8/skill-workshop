# Skill Workshop

![Skill Workshop](assets/thumbnail.jpg)

Get new skills for Hermes safely. Skill Workshop scans every skill before it is installed or used, including ones from other people, and it helps you mine skills from your past chats and build them from a description.

**New in 0.3.0:** Skill Workshop scans every skill before it is installed or used, including ones from other people. When Hermes writes a skill, or a file in your skills folder, the new text is scanned first and you see each finding (file and line) in the approval box. When a skill is loaded, it is scanned again: a skill with hidden text, instructions aimed at your agent, or commands that send secrets out is held back from the agent, and the agent tells you and waits for your decision (approve this exact version, or quarantine it). A skill added any other way (`hermes skills install`, copying a folder in) is scanned as soon as Hermes reports it, and at its first use. Ask "scan my installed skills" to see every skill as clean or flagged, with file and line. Your decisions are remembered by a hash of the skill's files, so a clean or approved skill is not asked about again, and any change to a file is scanned again. Skill Miner now names a mined skill from what you asked, and ignores the housekeeping calls (finding a skill, searching files) that open almost every chat.

**At a glance**

- **Who it is for:** people who want their Hermes agent to learn new skills, and who worry about what an imported skill or a web page could make the agent do.
- **Install:** `hermes plugins install flabanabba8/skill-workshop`, then `hermes plugins enable skill-workshop`, then restart Hermes.
- **Needs:** Hermes 0.22 or later. No API keys, no extra tools, no Python packages. Skill Miner needs some past Hermes sessions to look at.
- **Internet:** nothing. None of the four parts makes a network call or a model call of its own.
- **Platform:** Linux is the only platform checked.
- **Safety:** every skill is scanned for prompt injection before it is installed or used (a plain pattern check, not proof). Nothing is installed as a skill without a person confirming, a flagged skill is not handed to the agent until you decide, and the Shield and the Guard only block or ask; they never bypass a Hermes approval.

## The four parts

Skill Miner and Skill Builder are two ways to get a skill. Taint Shield sits with them because prompt injection is a real fear with imported skills and untrusted content: a skill, web page or file can hide instructions meant for your agent, not for you.

| Part | What it is for | Tools |
|---|---|---|
| **Skill Miner** | Looks through your recent Hermes sessions for sequences of tool calls you repeat, checks each on sessions held out of the mining, and drafts a skill for you to review. The host agent then diagnoses, refines and re-checks the draft. | `miner_scan`, `miner_propose`, `miner_diagnose`, `miner_refine`, `miner_check`, `miner_install` |
| **First Principles Skill Builder** | Helps the agent write a skill from a description so it fits the tools, hardware and permissions you actually have: it discovers resources, lints the draft, records three contrasting-case walk-throughs and keeps a revision history. | `skillbuilder_resources`, `skillbuilder_save`, `skillbuilder_check`, `skillbuilder_case`, `skillbuilder_install` |
| **Skill Guard** | Scans every skill before it is installed or used, including ones from other people. It checks what Hermes is about to write into the skills folder, checks each skill again when it is loaded (a flagged, unapproved one is replaced by a plain warning naming the findings), scans skills added by other routes when Hermes reports them, lists every installed skill as clean or flagged, and remembers your decisions by content hash. | `skillguard_scan_installed`, `skillguard_decide` |
| **Taint Shield** | A prompt-injection guard. It remembers which URLs, addresses and command lines came from untrusted web, browser, mail or file content, and blocks or asks before the agent uses them in a shell command, a file write or an outgoing message. | `shield_report`, `shield_scan`, `shield_trust` |

That is 16 tools, and five hooks: `pre_llm_call`, `post_tool_call`, `transform_tool_result`, `on_skill_lifecycle`, and `pre_tool_call` (registered four times: the Shield's check, the Guard's install scan, and the install approvals of Skill Miner and Skill Builder). Each part also registers its skill (`skill-miner`, `first-principles-skill-builder`, `taint-shield`, `skill-guard`). Nothing else is registered: no commands, no middleware, no desktop or dashboard surface.

Each part behaves exactly as its stand-alone plugin did; this repository bundles the three into one plugin so they can be installed together (Skill Guard is new in 0.3.0). A short example: ask Hermes "find a workflow I repeat and turn it into a skill" (Skill Miner), or "build me a skill that turns meeting recordings into notes on this machine" (Skill Builder). While either runs, the Shield watches what the agent reads and does.

## What each part does

### Skill Miner

You solve the same kinds of tasks again and again. Skill Miner reads Hermes's session database (opened read-only) for tool-call sequences that recur, checks that each holds up, and drafts a skill. It proposes only.

- `miner_scan` reads only tool names and counts. Sequences of 3 to 6 steps that appear in at least `min_support` sessions (default 3) are candidates (a two-step chore that writes a file is accepted when your requests share wording); housekeeping calls that open almost every chat (listing or viewing skills, searching tools or files) are left out, and candidates are ranked by what is specific to the job: your shared request words, the file types touched and the write steps. A drafted skill is named and described from your request; mining uses two thirds of your sessions and the rest are held out. A `recommend` verdict needs enough support, at least 75 percent consistency, and at least one held-out hit.
- `miner_propose` drafts a `SKILL.md` for one pattern, with abstracted typical arguments (paths, URLs, long ids and numbers replaced, secrets redacted by pattern) and up to three of your original request texts. This is the only step that reads message text.
- `miner_diagnose` returns bounded (8000 characters), redacted context for one proposal or revision for the host agent to reason over: structural problems in the draft and where its supporting sessions hit errors or retries.
- `miner_refine` saves the agent's revised text as a numbered revision beside the original, which is never modified.
- `miner_check` runs deterministic checks on a revision and replays its step order on held-out sessions. A weak mining verdict stays weak.
- `miner_install` writes the proposal into your skills folder as `<name>/SKILL.md`. A revision must have passed `miner_check` unchanged; it refuses to overwrite an existing skill and always asks a person to confirm.

Limits: it mines tool-name sequences, not intent, so a pattern is a habit and not necessarily a good skill; replay compares step order only; held-out checking is one deterministic split, not statistics; redaction is pattern based and can miss unusual secrets, so review a draft before sharing it. On the author's own 90-day history it found six candidate patterns and recommended none. That is the intended behaviour, not a failure.

### First Principles Skill Builder

You ask for a skill, or you have one that only works on one machine. The method is a registered skill: establish the goal and acceptance checks, discover resources before recommending, write the workflow with discovery, setup, authorization, acceptance and a degraded mode for each capability, then walk it through three contrasting cases (limited CPU and offline; capable GPU with cached models; a hosted service you explicitly chose). The reasoning is done by the host agent; the plugin adds five deterministic helpers.

- `skillbuilder_resources`: CPU count, RAM, free disk, NVIDIA GPU vendor and memory (via `nvidia-smi`), versions of a fixed list of common executables, cached model names, and the host's registered tools and skills. Names only: no model is loaded and no credential or account store is read.
- `skillbuilder_save`: save a draft as a new numbered revision. Earlier revisions are never overwritten.
- `skillbuilder_check`: one result per check, with offending lines (frontmatter, description quality, size, personal paths, mandatory provider ids, acceptance, degraded mode, retired workflows, harness neutrality, side effects without approval, referenced files and tools, recorded contrasting cases).
- `skillbuilder_case`: record the agent's walk-through of one contrasting case with a verdict (works, degraded, blocked).
- `skillbuilder_install`: install a clean, fully walked-through revision into your skills folder. It refuses failing checks, missing cases and overwrites, and always asks a person to confirm.

Limits: the checks are structural lint, not a judgment that a skill works; the walk-throughs are reasoning, not execution; GPU detection covers NVIDIA only.

### Skill Guard

Skills from other people can hide instructions meant for your agent. Skill Guard scans every skill, whoever wrote it, with the same plain pattern check as the Shield, line by line.

- **Before it is installed:** when Hermes writes a skill (`skill_manage`) or a file inside your skills folders, the new text is scanned first. A clean write goes through silently; a write with findings asks you, with every finding (file, line, what it is) in the approval text. Skills the workshop installs itself after a clean scan are recorded as clean.
- **When it is used:** when a skill is loaded, its files are scanned. A flagged version nobody has approved is not handed to the agent: it gets a plain warning naming the findings and is told not to follow those lines until you decide, and to tell you. You are told once per version. A `/skill-name` command is checked the same way and is stopped before the model sees the text.
- **Added another way:** `hermes skills install` and copying a folder in have no hook before they land, so Hermes reports the new skill afterwards and the Guard scans it then (and tells you at your next message); the use-time check holds it back either way.
- **Scan what you have:** `skillguard_scan_installed` ("scan my installed skills") lists every skill in your skills folders as clean, approved, quarantined or flagged, with file and line for each finding.
- **Your decisions:** `skillguard_decide` records approve (use it as it is) or quarantine (never hand it to the agent) for the exact current version, and always asks a person to confirm. Decisions are kept by content hash, so a clean or approved skill is never re-scanned or re-asked, and a changed file is scanned again.
- **Limits:** a pattern check, not proof; it cannot see a malicious skill that is rephrased, encoded or hidden in an image. Files the agent writes into the skills folder with a shell command are caught at their first use, not before.

### Taint Shield

Text the agent reads from the web, a browser, mail or similar sources is untrusted, and attackers hide instructions in it. Taint Shield remembers what came from untrusted content and stops the agent acting on it.

1. URLs, domains and addresses in your own messages are trusted for that session.
2. Output from tools whose names look like web, browser, fetch, mail, search, scrape, download and similar is untrusted; its URLs, domains, emails, IPs and command lines become tainted. Output with instruction-like phrases gets a one-line warning appended.
3. Before a sensitive tool runs (terminal, execute_code, send/post/email tools, write_file, patch, browser navigation or typing) its arguments are checked. It **blocks** reading local secrets and sending them out, editing login or startup files after untrusted content was read, running a command line copied from untrusted output, and using a tainted destination after an injection-like phrase. It **asks a person** before using a destination that appeared only in untrusted output. Everything else is untouched.
4. `shield_trust` adds a permanent trusted destination and always requires a person's approval, so injected text cannot trust itself. `shield_report` shows sources, flags and decisions per session; `shield_scan` analyses any text without changing anything, and with `path` it checks a skill file or folder you downloaded.
5. **Scan before install.** `miner_install` and `skillbuilder_install` scan the full draft first, using the Shield's own detection, line by line. A clean skill installs and the result says `scanned for prompt injection: no findings`. If anything is found (injection-like instructions, hidden zero-width text or instructions in an HTML comment, a command that sends or copies a secret or changes a login file, a download piped into a shell) nothing is installed and the result lists each finding with its line and how to go on: fix the draft, or repeat the install with `allow_findings` set, which still asks a person to approve and shows the findings in the approval text. Ordinary shell steps in a skill's own instructions are not flagged. The scan is on the same heuristic footing as the rest of the Shield: it reads only the draft's `SKILL.md` (the only file these two tools install), and a rephrased or encoded injection can slip past it.

Limits: this is heuristic provenance, not proof. It matches literal values, so an injection that makes the model rephrase or encode a destination can slip past; commands you also wrote are trusted; it only watches tools it recognises by name. It reduces risk, it does not make an agent safe to run on hostile content. It adds vetoes and approval requests only and bypasses no approval. Block rules are tuned on a small hand-written corpus, not a benchmark.

## Where the data goes

All four parts keep their data under one Hermes data folder, `plugin-data/skill-workshop/`, one sub-folder each: `skill-miner/proposals/`, `first-principles-skill-builder/drafts/`, `taint-shield/trusted.json` and `skill-guard/decisions.json` (a content hash, a skill name and a decision for each skill version; no skill text). Data written by the stand-alone plugins (under `plugin-data/skill-miner/` and so on) is not read or migrated. Installing a skill writes one new `<HERMES_HOME>/skills/<name>/SKILL.md`, and only after you confirm.

## Limits of the suite

- Linux is the only platform checked.
- The desktop and dashboard surfaces are not part of this plugin; none of the parts has one.
- Taint Shield guards the tool calls of the whole Hermes session, not only the other two parts. It can ask or block on ordinary work that follows untrusted content; trust a destination with `shield_trust` if you want it to stop asking.
- Live evidence for each part is the part's own (see VERIFICATION.md). The suite itself was tested offline plus the Hermes admission check.

## Credits and licence

No third-party code or data is bundled: all four parts are original code with no vendored libraries, no downloaded tools and no media. The plugin does not use TMDB, ani-cli, Luffy, Live2D or any other upstream tool. Licence: GPL-3.0-or-later (see LICENSE).

**AI assistance:** written with AI coding assistants (Anthropic Claude and OpenAI Codex agents) under the maintainer's direction; what was actually tested is listed in VERIFICATION.md.
