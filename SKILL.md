---
name: dream-consolidator
description: Bypasses the broken OpenClaw dreaming pipeline and runs a full manual Light → REM → Deep memory consolidation sweep as an agentic turn. Trigger whenever the user says "dream", "consolidate memory", "run dreaming", "promote memories", "dream run", or "go to sleep". Also trigger automatically if no dream consolidation has run in the last 24 hours. This skill is the ONLY way to produce DREAMS.md and promote atomic memory nodes until the upstream generateAndAppendDreamNarrative bug is fixed in OpenClaw. Always use this skill instead of /dreaming run.
---

# Dream Consolidator

Replaces the broken OpenClaw `generateAndAppendDreamNarrative` TypeScript function.
Runs the full Light → REM → Deep sweep as pure agentic reasoning.
Writes atomic memory nodes + `DREAMS.md` in Obsidian format.

---

## What This Skill Does

OpenClaw's built-in dreaming pipeline receives empty `snippets` and `promotions`
arrays and never writes `DREAMS.md`. This skill does the same job manually:

0. **PRE-PROCESS** — Run `dream.py` to extract SQLite chunks → clean .md files
1. **LIGHT** — Read 7 days of memory files, deduplicate, stage candidates
2. **REM** — Find hidden connections and recurring patterns across candidates
3. **DEEP** — Score candidates, promote survivors as atomic nodes
4. **DIARY** — Append narrative entry to `DREAMS.md`

---

## Execution Protocol

### PHASE 0 — PRE-PROCESSING

Run `dream.py` before anything else. It extracts OpenClaw's SQLite memory
database into dated Markdown files and scrubs each one for PII and secrets.

**Auto-detects all paths — no configuration needed for standard installs.**

```
python dream.py
```

Or with explicit workspace override:

```
OPENCLAW_WORKSPACE=/path/to/workspace python dream.py
```

Dry-run (preview scrub only, no writes):

```
python dream.py --dry-run
```

Print resolved paths and exit:

```
python dream.py --config
```

**Watch for the ready signal:**
```
[HH:MM:SS] === ✅ memory\ ready. Dream Consolidator can fire. ===
```

**If any step fails** — the script exits with code 1 and prints which step broke.
Do not proceed to Phase 1 if Phase 0 fails. Fix the error first.

---

### PHASE 1 — LIGHT SLEEP (Ingestion)

Read the last 7 days of memory files. Use `memory_get` or `read` on each.

Extract every meaningful signal:
- Decisions made
- Problems solved
- Tools used
- Preferences expressed
- Recurring questions
- Corrections given

**Deduplicate:** entries >80% similar → keep only the most recent.

Build a candidate list:
```
CANDIDATE: <topic>
SOURCE: memory/YYYY-MM-DD.md
SIGNAL: <why this matters>
HITS: <how many times seen across 7 days>
```

---

### PHASE 2 — REM SLEEP (Pattern Finding)

Look across all candidates and ask:

1. What topics keep appearing? (recurring = 3+ days)
2. What connections exist between topics that haven't been explicitly made?
3. What is the user actually trying to build or solve at a deeper level?
4. What preferences or patterns have been shown without being stated directly?
5. What has changed or evolved over 7 days?

Output:
- Recurring themes
- Hidden connections discovered
- Candidate truths (things that keep being true)
- Low-signal items to discard

---

### PHASE 3 — DEEP SLEEP (Promotion)

Score each candidate truth on 6 signals:

| Signal | Weight | Question |
|--------|--------|----------|
| Relevance | 30% | Useful in future sessions? |
| Frequency | 24% | Appeared 3+ days? |
| Query Diversity | 15% | Came up in 3+ contexts? |
| Recency | 15% | Still true today? |
| Consolidation | 10% | Connects to existing nodes? |
| Conceptual Richness | 6% | Insight vs. plain fact? |

**Promotion gate — ALL THREE must pass:**
- Score ≥ 0.8
- Seen on 3+ different days
- Appeared in 3+ different query contexts

**Promoted node format** → `memory/YYMMDD-dream-<slug>.md`:

```markdown
---
date: YYYY-MM-DD
tags: [memory, dream, <topic-tag>]
status: active
project: <project>
source: dream-consolidator
score: <0.0–1.0>
aliases: [<topic>]
---

# <Topic Title>

<2–3 sentences of what was learned/understood>

## Evidence
- memory/file.md — what it said
- memory/file2.md — what it said

## Related
[[existing-node]]

## Date
[[YYYY-MM-DD]]
```

---

### PHASE 4 — DREAM DIARY

After all phases complete, append to `DREAMS.md`:

```markdown
## Dream Cycle — YYYY-MM-DD HH:MM

### 💤 Light Sleep
- Candidates staged: <N>
- Sources read: memory/ × 7 days
- Duplicates removed: <N>

### 🌀 REM Sleep
- Recurring themes: <list>
- Hidden connections: <list>
- Candidate truths: <N>

### 🌑 Deep Sleep
- Promoted: <N> nodes → memory/YYMMDD-dream-*.md
- Discarded: <N> (reason)
- Promoted topics: <list>

### 📖 Narrative
<3–5 sentences in first person from the agent's perspective:
what was understood, what was surprising, what was discarded and why.>
```

---

## Confirmation Step

Before writing ANY nodes, show the user:

```
🌙 DREAM CONSOLIDATOR — Ready to promote

Candidates found: <N>
Will promote: <N> nodes
Will discard: <N>

PROMOTING:
✅ <topic> (score: 0.87) → memory/YYMMDD-dream-<slug>.md
✅ <topic> (score: 0.83) → memory/YYMMDD-dream-<slug>.md

DISCARDING:
❌ <topic> (score: 0.61) — below threshold
❌ <topic> (score: 0.44) — single day only

Proceed? (yes / no / edit)
```

Wait for confirmation before writing.

---

## Hard Rules

1. Never delete existing memory nodes — only add new ones
2. Never promote a single-day observation — must span 3+ days
3. Never promote noise — if it wouldn't help in a future session, discard
4. Always confirm before writing — show the candidate list first
5. If 7 days of notes don't exist — use what exists, note the gap
6. Score must be calculated explicitly — show the math, never guess

---

## Path Auto-Detection

`dream.py` resolves all paths automatically:

| Path | Default |
|------|---------|
| SQLite DB | `~/.openclaw/memory/main.sqlite` |
| Memory dir | `~/.openclaw/workspace/memory/` |
| Reports dir | `~/.openclaw/workspace/PROJECTS/chatlog-pipeline/reports/` |
| Allowed root | `~/.openclaw/workspace/` |

Override with environment variables:

| Variable | Purpose |
|----------|---------|
| `OPENCLAW_HOME` | Override `~/.openclaw` |
| `OPENCLAW_WORKSPACE` | Override workspace root |
| `DREAM_LOCK_WAIT` | SQLite wait in seconds (default: 6) |
| `DREAM_NAMES_LIST` | Path to names redaction list |
| `DREAM_CUSTOM_LIST` | Path to custom terms redaction list |

---

## Evaluation Criteria

This skill worked correctly if:
1. At least one atomic node was written to `memory/`
2. `DREAMS.md` has a new entry with a narrative
3. The promoted node reads like something the user would have written themselves
4. No noise was promoted — every node is genuinely useful in a future session
5. The REM narrative surfaces a connection that hadn't been consciously named
