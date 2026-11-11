---
name: timestamped-transcript
description: Turn a recorded talk or meeting into a transcript with per-segment timestamps and a review of low-confidence spans. Use when the user hands over an audio or video file and needs text that can be cited by time.
---

# Timestamped transcript

Goal: text of what was said, each segment with start and end seconds, plus a list of
spans the recognizer was unsure about. Inputs: one audio or video file, a language
(ask only if not obvious from the file name or the user's messages).

## Choose a recognizer

1. Discover. Look for an installed recognizer that returns segment timestamps (for
   example a whisper-family command line tool or Python package) and for ffmpeg to
   extract audio. Run its help or version command; do not load a model yet.
2. Prefer a local recognizer that fits memory. On a small CPU-only machine pick the
   smallest model that meets the quality the user asked for and tell them the wait.
   With a capable GPU and a cached larger model, use it. Cached means already on disk;
   downloading a model is a separate choice to ask about, with its size.
3. A hosted recognizer is used only if the user selected one, after confirming that
   the audio may be uploaded and the per-job spend limit (zero is valid).
4. A recognizer that returns plain text without timestamps does not meet the goal.

## Do the work

Extract mono 16 kHz audio, transcribe, and write segments as `start end text`.
Mark any segment whose confidence is below the recognizer's own reported threshold.

## Acceptance

Verify before reporting: the last segment ends within two seconds of the file
duration, no gaps over ten seconds unless the audio is silent there, and every
segment has start < end. Report the recognizer, model and device actually used.

## Degraded mode and blockers

If no recognizer with timestamps exists, stop with a setup choice: which local tool
could be installed (with its size) or which hosted service the user could select.
If only a plain-text recognizer exists, offer text without timestamps and say plainly
that it cannot be cited by time. Never invent timestamps by splitting evenly.
