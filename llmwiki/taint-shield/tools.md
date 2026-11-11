# Actual tool contracts

Registered source schemas; registration alone does not establish live backend readiness.

## shield_report

Show what Taint Shield has seen in a session: untrusted sources, injection-like phrases and the actions it blocked or sent for approval.

Inputs: `session_id` (optional).

## shield_scan

Scan a piece of text for URLs, addresses, command lines and injection-like phrases without changing anything. Or give `path` (a downloaded skill file or folder) to check a skill, and its bundled text files, for prompt injection before installing it: findings come back by file and line.

Inputs: `text` or `path` (give one).

## shield_trust

Add a domain, address or URL to the permanent trusted list. Always requires a person to confirm.

Inputs: `value` (required).

