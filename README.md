# openclaw-dream-con# dream.py — working memory pre-processor for OpenClaw

OpenClaw's built-in `/dreaming run` does nothing. The `generateAndAppendDreamNarrative`
function receives empty arrays and exits silently. Your memory stays flat.

`dream.py` fixes the pre-processing step. It reads OpenClaw's internal SQLite database,
extracts all indexed memory chunks as clean Markdown files, and scrubs each one for API
keys, tokens, and PII before anything else touches them. One file, no dependencies,
auto-detects your paths.

---

## Install

**Step 1** — drop `dream.py` into your workspace:

```
workspace/
└── dream.py
```

**Step 2** — make sure the reports directory exists:

```bash
mkdir -p ~/.openclaw/workspace/PROJECTS/chatlog-pipeline/reports
```

That's it. No pip installs. Python 3.9+ stdlib only.

---

## Run

```bash
python dream.py
```

Auto-detects `~/.openclaw/memory/main.sqlite` and writes extracted chunks to
`~/.openclaw/workspace/memory/`. When it's done:

```
[22:12:59] === dream.py — pipeline start ===
[22:12:59] SQLite:   /home/<you>/.openclaw/memory/main.sqlite
[22:12:59] Memory:   /home/<you>/.openclaw/workspace/memory
[22:12:59] Reports:  /home/<you>/.openclaw/workspace/PROJECTS/chatlog-pipeline/reports
[22:12:59] ▶ SQLite extraction
[22:12:59] Found 226 chunks with content
[22:12:59] Extraction complete: 226 new file(s) written
[22:12:59] ✓ SQLite extraction done — 226 new file(s)
[22:12:59] Sleeping 6s — SQLite releasing lock...
[22:13:05] ▶ Scrubbing 226 file(s)
[22:13:05]   ✓ 20260501-memory-md.md — clean
[22:13:05]   ✓ 20260430-memory-stack-index-md.md — clean
...
[22:13:06] ✓ Scrub complete — 0 total redaction(s) across 226 file(s)
[22:13:06] === ✅ memory\ ready. Dream Consolidator can fire. ===
```

Once you see `✅ memory\ ready` — trigger your agent's dream sweep.

---

## Output

**Extracted memory file** (`memory/20260501-memory-stack-index-md.md`):

```markdown
---
date: 2026-05-01
tags: [memory, extracted, memory]
status: open
project: jarvis
source: sqlite-extraction
origin_path: memory/stack-index.md
---

# Extracted Memory — memory/stack-index.md

<raw text from the chunks table>

## Related

## Date
[[2026-05-01]]
```

**Scrub report** (`PROJECTS/chatlog-pipeline/reports/<stem>-scrub-report.md`):

```markdown
# Scrub Report — 2026-05-01T22:13:05

**File:** `memory/20260501-memory-stack-index-md.md`
**Total redactions:** 1

## By type
- GROQ_KEY: 1

## Detail
| Line | Tier   | Type     | Hint       | Replacement        |
|------|--------|----------|------------|--------------------|
| 14   | TIER_1 | GROQ_KEY | `gsk_xA3b` | `[REDACTED_GROQ_KEY]` |
```

One report per file. Hints show the first 8 characters only — never the full secret.

---

## Three CLI flags

**`--dry-run`** — run the full scrub pass and print what would be redacted, without
writing or modifying any file:

```bash
python dream.py --dry-run
```solidator
