---
name: project-context-discovery
description: Use when starting an unfamiliar repository task and you need to identify applicable guidance and locate the files relevant to the requested change before acting.
---

# Discover project context before acting

1. `skills_list` - Check whether an existing relevant skill covers the task; load it before proceeding if it does.
2. `search_files` - Find repository guidance and likely target files by name. Narrow searches using the task's key symbols or file types rather than dumping the entire tree.
3. `read_file` - Read applicable project instructions and the relevant source files before editing. Trace definitions and usages where needed.

## Use the findings

- Follow repository instructions (for example, AGENTS.md) and any applicable skill before changing files.
- Inspect manifests and neighboring code before assuming APIs, dependencies, or conventions.
- If the search is empty or too broad, refine the query and search again; do not invent paths or symbols.
- Keep this discovery read-only. Make only task-scoped changes after understanding the relevant context, then run suitable verification.
- Do not read secrets or unrelated profiles, and preserve original inputs.