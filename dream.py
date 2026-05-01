#!/usr/bin/env python3
"""
dream.py — OpenClaw Dream Consolidator (consolidated single-file edition)

Merges orchestrator.py + main SQLite memory read.py + scrub.py into one script.
No subprocess calls. No external dependencies. Python 3.9+ stdlib only.

Pipeline:
    1. Auto-detect OpenClaw paths (SQLite DB, memory dir, reports dir)
    2. Extract chunks table → dated .md files in memory/
    3. Wait for SQLite lock to release
    4. Scrub each new file for PII and secrets (in-place)
    5. Write per-file scrub reports
    6. Print ✅ ready signal — agent agentic sweep can begin

Usage:
    python dream.py                  # auto-detect all paths
    python dream.py --dry-run        # scrub preview only, no writes
    python dream.py --config         # print resolved config and exit
"""

import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — auto-detected from environment, override here if needed
# ══════════════════════════════════════════════════════════════════════════════

def resolve_config() -> dict:
    """
    Auto-detect all paths from the environment.

    Detection order:
      1. OPENCLAW_HOME env var (explicit override)
      2. Default per-OS location (~/.openclaw)

    All paths are resolved and validated here. The rest of the script uses
    only the returned config dict — no hardcoded paths anywhere else.
    """
    # Base OpenClaw data directory
    home = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))

    # Workspace root — where memory/, DREAMS.md, and skills/ live
    workspace = Path(
        os.environ.get("OPENCLAW_WORKSPACE", home.parent / ".openclaw" / "workspace")
    )
    # Fallback: if workspace doesn't exist, try sibling of home
    if not workspace.exists():
        workspace = home.parent / "workspace"
    # Second fallback: home/../workspace
    if not workspace.exists():
        workspace = Path.home() / ".openclaw" / "workspace"

    sqlite_path  = home / "memory" / "main.sqlite"
    memory_dir   = workspace / "memory"
    reports_dir  = workspace / "PROJECTS" / "chatlog-pipeline" / "reports"
    dreams_file  = workspace / "DREAMS.md"
    allowed_root = workspace

    return {
        "sqlite_path":  sqlite_path,
        "memory_dir":   memory_dir,
        "reports_dir":  reports_dir,
        "dreams_file":  dreams_file,
        "allowed_root": allowed_root,
        "lock_wait_s":  int(os.environ.get("DREAM_LOCK_WAIT", "6")),
        "names_list":   Path(os.environ["DREAM_NAMES_LIST"]) if "DREAM_NAMES_LIST" in os.environ else None,
        "custom_list":  Path(os.environ["DREAM_CUSTOM_LIST"]) if "DREAM_CUSTOM_LIST" in os.environ else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — EXTRACT (from main SQLite memory read.py)
# ══════════════════════════════════════════════════════════════════════════════

def extract_chunks(sqlite_path: Path, memory_dir: Path) -> list[Path]:
    """
    Read all rows from the chunks table in main.sqlite.
    Write each as a dated .md file to memory_dir.
    Returns list of newly written file paths (skips existing).
    """
    if not sqlite_path.exists():
        die(f"SQLite database not found: {sqlite_path}\n  Has OpenClaw indexed at least one session?")

    memory_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Verify chunks table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in cursor.fetchall()]
    log(f"Tables found: {tables}")

    if "chunks" not in tables:
        conn.close()
        die("'chunks' table not found in main.sqlite. Cannot extract memory.")

    cursor.execute(
        "SELECT path, source, text, updated_at FROM chunks "
        "WHERE text IS NOT NULL AND text != ''"
    )
    rows = cursor.fetchall()
    conn.close()

    log(f"Found {len(rows)} chunks with content")

    written: list[Path] = []
    seen_slugs: dict[str, int] = {}

    for row in rows:
        path    = row["path"] or "unknown"
        source  = row["source"] or "memory"
        content = row["text"].strip()
        ts      = row["updated_at"]

        if not content:
            continue

        # Resolve timestamp (milliseconds epoch)
        try:
            date_obj = datetime.fromtimestamp(int(ts) / 1000) if ts else datetime.now()
        except Exception:
            date_obj = datetime.now()

        date_str  = date_obj.strftime("%Y-%m-%d")
        file_date = date_obj.strftime("%Y%m%d")

        # Build collision-safe filename from origin path
        slug = "".join(c if c.isalnum() else "-" for c in path.lower()).strip("-")[:60]
        if not slug:
            slug = "extract"

        seen_slugs[slug] = seen_slugs.get(slug, 0) + 1
        idx    = seen_slugs[slug]
        suffix = f"-{idx}" if idx > 1 else ""
        target = memory_dir / f"{file_date}-{slug}{suffix}.md"

        # Idempotent — skip if already extracted
        if target.exists():
            continue

        md = (
            f"---\n"
            f"date: {date_str}\n"
            f"tags: [memory, extracted, {source}]\n"
            f"status: open\n"
            f"project: jarvis\n"
            f"source: sqlite-extraction\n"
            f"origin_path: {path}\n"
            f"---\n\n"
            f"# Extracted Memory — {path}\n\n"
            f"{content}\n\n"
            f"## Related\n\n"
            f"## Date\n"
            f"[[{date_str}]]\n"
        )

        target.write_text(md, encoding="utf-8")
        written.append(target)

    log(f"Extraction complete: {len(written)} new file(s) written")
    return written


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — SCRUB (from scrub.py)
# ══════════════════════════════════════════════════════════════════════════════

# ── Tier 1: High-confidence — API keys, tokens, credentials ──────────────────
TIER_1_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("GROQ_KEY",           re.compile(r"gsk_[A-Za-z0-9]{40,}")),
    ("OPENAI_PROJ_KEY",    re.compile(r"sk-proj-[A-Za-z0-9_\-]{40,}")),
    ("OPENAI_KEY",         re.compile(r"sk-[A-Za-z0-9]{20,}(?!-proj)")),
    ("ANTHROPIC_KEY",      re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,}")),
    ("HUGGINGFACE_TOKEN",  re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("GITHUB_TOKEN",       re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("TELEGRAM_TOKEN",     re.compile(r"\d{8,10}:[A-Za-z0-9_\-]{35}")),
    ("CLOUDINARY_URL",     re.compile(r"cloudinary://\d+:[A-Za-z0-9_\-]+@[a-z0-9\-]+")),
    ("DISCORD_WEBHOOK",    re.compile(r"https://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]+")),
    ("SLACK_WEBHOOK",      re.compile(r"https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[A-Za-z0-9]+")),
    ("TELEGRAM_API_URL",   re.compile(r"https://api\.telegram\.org/bot[^/\s]+")),
    ("JWT",                re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("GENERIC_BEARER",     re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
    ("GENERIC_AUTH_PARAM", re.compile(r"(?i)(?:api[_\-]?key|token|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{20,})['\"]?")),
]

# ── Tier 2: Moderate-confidence — PII ────────────────────────────────────────
TIER_2_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL",              re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("PHONE_DE",           re.compile(r"\+49[\s\-]?\d{2,4}[\s\-]?\d{3,}[\s\-]?\d{3,}")),
    ("PHONE_GR",           re.compile(r"\+30[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{4}")),
    ("PHONE_INTL",         re.compile(r"\+\d{1,3}[\s\-]?\d{6,14}")),
    ("BERLIN_ADDRESS",     re.compile(r"\b1\d{4}\s+Berlin\b")),
]


def _load_list(path: Path | None) -> list[str]:
    """Load a newline-separated list file. Returns [] if path is None or missing."""
    if not path or not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            items.append(line)
    return items


def scrub_text(
    text: str,
    names: list[str],
    custom: list[str],
) -> tuple[str, list[dict]]:
    """
    Apply all three tiers of redaction patterns.
    Returns (scrubbed_text, list_of_redaction_dicts).
    Each dict: {line, tier, type, hint, replacement}
    """
    redactions: list[dict] = []
    lines = text.splitlines(keepends=True)

    def apply_patterns(patterns: list[tuple[str, re.Pattern]], tier: str) -> None:
        for type_name, pattern in patterns:
            for i in range(len(lines)):
                def _replace(m: re.Match, tn: str = type_name, t: str = tier) -> str:
                    fragment = m.group(0)
                    hint = fragment[:8] + "..." if len(fragment) > 8 else fragment
                    repl = f"[REDACTED_{tn}]"
                    redactions.append({"line": i + 1, "tier": t, "type": tn, "hint": hint, "replacement": repl})
                    return repl
                lines[i] = pattern.sub(_replace, lines[i])

    apply_patterns(TIER_1_PATTERNS, "TIER_1")
    apply_patterns(TIER_2_PATTERNS, "TIER_2")

    # Tier 3 — user-maintained literal lists
    for name in names:
        if not name:
            continue
        pat = re.compile(re.escape(name), re.IGNORECASE)
        for i in range(len(lines)):
            def _replace_name(m: re.Match, n: str = name) -> str:
                redactions.append({"line": i + 1, "tier": "TIER_3", "type": "CLIENT_NAME",
                                   "hint": n[:3] + "***", "replacement": "[REDACTED_NAME]"})
                return "[REDACTED_NAME]"
            lines[i] = pat.sub(_replace_name, lines[i])

    for term in custom:
        if not term:
            continue
        pat = re.compile(re.escape(term), re.IGNORECASE)
        for i in range(len(lines)):
            def _replace_custom(m: re.Match, t: str = term) -> str:
                redactions.append({"line": i + 1, "tier": "TIER_3", "type": "CUSTOM",
                                   "hint": t[:3] + "***", "replacement": "[REDACTED_CUSTOM]"})
                return "[REDACTED_CUSTOM]"
            lines[i] = pat.sub(_replace_custom, lines[i])

    return "".join(lines), redactions


def _build_scrub_report(
    md_file: Path,
    redactions: list[dict],
) -> str:
    """Build a markdown scrub report string."""
    ts    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    total = len(redactions)

    by_type: dict[str, int] = {}
    for r in redactions:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    out = [
        f"# Scrub Report — {ts}",
        "",
        f"**File:** `{md_file}`",
        f"**Total redactions:** {total}",
        "",
    ]
    if by_type:
        out += ["## By type", ""]
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            out.append(f"- {t}: {c}")
        out.append("")
    if redactions:
        out += ["## Detail", "", "| Line | Tier | Type | Hint | Replacement |",
                "|------|------|------|------|-------------|"]
        for r in redactions:
            out.append(f"| {r['line']} | {r['tier']} | {r['type']} | `{r['hint']}` | `{r['replacement']}` |")
        out.append("")
    out += ["---", "", "Hints show first chars only — never the full secret.", ""]
    return "\n".join(out)


def scrub_file(
    md_file: Path,
    reports_dir: Path,
    names: list[str],
    custom: list[str],
    dry_run: bool = False,
) -> int:
    """
    Scrub a single .md file in-place.
    Writes report to reports_dir/<stem>-scrub-report.md.
    Returns redaction count.
    """
    text = md_file.read_text(encoding="utf-8")
    scrubbed, redactions = scrub_text(text, names, custom)
    report_str = _build_scrub_report(md_file, redactions)

    if not dry_run:
        md_file.write_text(scrubbed, encoding="utf-8")
        report_path = reports_dir / f"{md_file.stem}-scrub-report.md"
        report_path.write_text(report_str, encoding="utf-8")

    return len(redactions)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE (from orchestrator.py)
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(dry_run: bool = False) -> None:
    cfg = resolve_config()

    log("=== dream.py — pipeline start ===")
    if dry_run:
        log("DRY-RUN mode — no files will be written or modified")

    # Print resolved paths so the agent / user can verify
    log(f"SQLite:   {cfg['sqlite_path']}")
    log(f"Memory:   {cfg['memory_dir']}")
    log(f"Reports:  {cfg['reports_dir']}")

    # ── Step 1: Snapshot memory/ before extraction ────────────────────────────
    before: set[Path] = set(cfg["memory_dir"].glob("*.md")) if cfg["memory_dir"].exists() else set()

    # ── Step 2: Extract SQLite → .md files ───────────────────────────────────
    log("▶ SQLite extraction")
    if dry_run:
        log("  (dry-run: extraction skipped)")
        new_files: list[Path] = []
    else:
        new_files = extract_chunks(cfg["sqlite_path"], cfg["memory_dir"])

    log(f"✓ SQLite extraction done — {len(new_files)} new file(s)")

    # ── Step 3: Wait for SQLite lock to release ───────────────────────────────
    wait = cfg["lock_wait_s"]
    log(f"Sleeping {wait}s — SQLite releasing lock...")
    time.sleep(wait)

    # ── Step 4: Scrub new files ───────────────────────────────────────────────
    if not new_files:
        log("⚠️  No new files — nothing to scrub.")
    else:
        log(f"▶ Scrubbing {len(new_files)} file(s)")

        if not dry_run:
            cfg["reports_dir"].mkdir(parents=True, exist_ok=True)

        names  = _load_list(cfg["names_list"])
        custom = _load_list(cfg["custom_list"])

        total_redactions = 0
        for md_file in new_files:
            count = scrub_file(md_file, cfg["reports_dir"], names, custom, dry_run=dry_run)
            total_redactions += count
            status = f"{count} redaction(s)" if count else "clean"
            log(f"  ✓ {md_file.name} — {status}")

        log(f"✓ Scrub complete — {total_redactions} total redaction(s) across {len(new_files)} file(s)")

    # ── Step 5: Ready signal ──────────────────────────────────────────────────
    log("=== ✅ memory\\ ready. Dream Consolidator can fire. ===")


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="OpenClaw Dream Consolidator pre-processor — extract + scrub memory chunks."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview scrub output without writing any files."
    )
    parser.add_argument(
        "--config", action="store_true",
        help="Print resolved configuration and exit."
    )
    args = parser.parse_args()

    if args.config:
        cfg = resolve_config()
        print("\nResolved configuration:")
        for k, v in cfg.items():
            print(f"  {k:<15} {v}")
        print()
        sys.exit(0)

    run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
