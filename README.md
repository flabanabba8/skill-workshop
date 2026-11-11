# Skill Workshop

Get new skills for Hermes safely: mine them from your past chats, build them from a description, and guard against prompt injection in skills and content you bring in.

**At a glance**

- **Who it is for:** people who want their Hermes agent to learn new skills, and who worry about what an imported skill or a web page could make the agent do.
- **Install:** `hermes plugins install flabanabba8/skill-workshop`, then `hermes plugins enable skill-workshop`, then restart Hermes.
- **Needs:** Hermes 0.22 or later. No API keys, no extra tools, no Python packages. Skill Miner needs some past Hermes sessions to look at.
- **Internet:** nothing. None of the three parts makes a network call or a model call of its own.
- **Platform:** Linux is the only platform checked.
- **Safety:** nothing is installed as a skill without a person confirming, and the Shield only blocks or asks; it never bypasses a Hermes approval.

## The three parts

Skill Miner and Skill Builder are two ways to get a skill. Taint Shield sits with them because prompt injection is a real fear with imported skills and untrusted content: a skill, web page or file can hide instructions meant for your agent, not for you.

| Part | What it is for | Tools |
|---|---|---|
| **Skill Miner** | Looks through your recent Hermes sessions for sequences of tool calls you repeat, checks each on sessions held out of the mining, and drafts a skill for you to review. The host agent then diagnoses, refines and re-checks the draft. | `miner_scan`, `miner_propose`, `miner_diagnose`, `miner_refine`, `miner_check`, `miner_install` |
| **First Principles Skill Builder** | Helps the agent write a skill from a description so it fits the tools, hardware and permissions you actually have: it discovers resources, lints the draft, records three contrasting-case walk-throughs and keeps a revision history. | `skillbuilder_resources`, `skillbuilder_save`, `skillbuilder_check`, `skillbuilder_case`, `skillbuilder_install` |
| **Taint Shield** | A prompt-injection guard. It remembers which URLs, addresses and command lines came from untrusted web, browser, mail or file content, and blocks or asks before the agent uses them in a shell command, a file write or an outgoing message. | `shield_report`, `shield_scan`, `shield_trust` |

That is 14 tools, and four hooks: `pre_llm_call`, `post_tool_call`, `transform_tool_result`, and `pre_tool_call` (registered three times: the Shield's check, and the install approvals of Skill Miner and Skill Builder). Each part also registers its skill (`skill-miner`, `first-principles-skill-builder`, `taint-shield`). Nothing else is registered: no commands, no middleware, no desktop or dashboard surface.

Each part behaves exactly as its stand-alone plugin did; this repository bundles the three into one plugin so they can be installed together. A short example: ask Hermes "find a workflow I repeat and turn it into a skill" (Skill Miner), or "build me a skill that turns meeting recordings into notes on this machine" (Skill Builder). While either runs, the Shield watches what the agent reads and does.

## What each part does

### Skill Miner

You solve the same kinds of tasks again and again. Skill Miner reads Hermes's session database (opened read-only) for tool-call sequences that recur, checks that each holds up, and drafts a skill. It proposes only.

- `miner_scan` reads only tool names and counts. Sequences of 3 to 6 steps that appear in at least `min_support` sessions (default 3) are candidates; mining uses two thirds of your sessions and the rest are held out. A `recommend` verdict needs enough support, at least 75 percent consistency, and at least one held-out hit.
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

### Taint Shield

Text the agent reads from the web, a browser, mail or similar sources is untrusted, and attackers hide instructions in it. Taint Shield remembers what came from untrusted content and stops the agent acting on it.

1. URLs, domains and addresses in your own messages are trusted for that session.
2. Output from tools whose names look like web, browser, fetch, mail, search, scrape, download and similar is untrusted; its URLs, domains, emails, IPs and command lines become tainted. Output with instruction-like phrases gets a one-line warning appended.
3. Before a sensitive tool runs (terminal, execute_code, send/post/email tools, write_file, patch, browser navigation or typing) its arguments are checked. It **blocks** reading local secrets and sending them out, editing login or startup files after untrusted content was read, running a command line copied from untrusted output, and using a tainted destination after an injection-like phrase. It **asks a person** before using a destination that appeared only in untrusted output. Everything else is untouched.
4. `shield_trust` adds a permanent trusted destination and always requires a person's approval, so injected text cannot trust itself. `shield_report` shows sources, flags and decisions per session; `shield_scan` analyses any text without changing anything.

Limits: this is heuristic provenance, not proof. It matches literal values, so an injection that makes the model rephrase or encode a destination can slip past; commands you also wrote are trusted; it only watches tools it recognises by name. It reduces risk, it does not make an agent safe to run on hostile content. It adds vetoes and approval requests only and bypasses no approval. Block rules are tuned on a small hand-written corpus, not a benchmark.

## Where the data goes

All three parts keep their data under one Hermes data folder, `plugin-data/skill-workshop/`, one sub-folder each: `skill-miner/proposals/`, `first-principles-skill-builder/drafts/` and `taint-shield/trusted.json`. Data written by the stand-alone plugins (under `plugin-data/skill-miner/` and so on) is not read or migrated. Installing a skill writes one new `<HERMES_HOME>/skills/<name>/SKILL.md`, and only after you confirm.

## Limits of the suite

- Linux is the only platform checked.
- The desktop and dashboard surfaces are not part of this plugin; none of the three parts had one.
- Taint Shield guards the tool calls of the whole Hermes session, not only the other two parts. It can ask or block on ordinary work that follows untrusted content; trust a destination with `shield_trust` if you want it to stop asking.
- Live evidence for each part is the part's own (see VERIFICATION.md). The suite itself was tested offline plus the Hermes admission check.

## Credits and licence

No third-party code or data is bundled: all three parts are original code with no vendored libraries, no downloaded tools and no media. The plugin does not use TMDB, ani-cli, Luffy, Live2D or any other upstream tool. Licence: GPL-3.0-or-later (see LICENSE).

**AI assistance:** written with AI coding assistants (Anthropic Claude and OpenAI Codex agents) under the maintainer's direction; what was actually tested is listed in VERIFICATION.md.
