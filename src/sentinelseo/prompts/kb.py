"""Knowledge base for stack-specific fix guidance.

The prompt engine is deterministic by design, but it cannot ship hand-written
guidance for every (check × stack) pair — 267 checks across 9 stack profiles is
over two thousand combinations, most of which never occur. This module is how
the system fills that space *once* and then remembers.

Flow for one prompt:

    hand-written family guidance  →  KB lookup  →  (miss + AI configured)
                                                   generate once, store, reuse

Properties that matter more than cleverness here:

* **Deterministic fallback.** With no AI key the system still produces a correct
  prompt from the family template. AI only ever *upgrades* a prompt.
* **Inspectable.** Rows are plain SQLite: readable, editable, deletable. A bad
  generation is one UPDATE away from fixed, and `source='manual'` rows always
  win over generated ones.
* **Bounded cost.** Each pair is generated at most once, ever.
* **Never blocks an audit.** Every failure path returns None and the caller
  falls back to the template.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sentinelseo.db.models import PromptKB
from sentinelseo.db.session import SessionLocal

# A generated row must look like implementation guidance, not an essay or a
# refusal. Anything outside these bounds is rejected rather than cached.
MIN_LEN = 60
MAX_LEN = 1400

# Never cache guidance that would have an agent run something destructive.
BANNED = (
    "rm -rf", "drop table", "drop database", "truncate table", "mkfs",
    "chmod 777", "git push --force", "> /dev/sd", "dd if=", "shutdown",
    ":(){", "curl | sh", "wget | sh", "eval(",
)


def _clean(text: str) -> Optional[str]:
    """Validate a generated block before it is ever stored or shown."""
    t = (text or "").strip()
    if not (MIN_LEN <= len(t) <= MAX_LEN):
        return None
    low = t.lower()
    if any(b in low for b in BANNED):
        return None
    # A model that declined the task must not be cached as advice.
    if low.startswith(("i cannot", "i can't", "i'm sorry", "as an ai")):
        return None
    return t


def lookup(check_id: str, stack: str) -> Optional[str]:
    """Return cached guidance for this pair, preferring human-authored rows."""
    db = SessionLocal()
    try:
        rows = (
            db.query(PromptKB)
            .filter(PromptKB.check_id == check_id, PromptKB.stack == stack)
            .all()
        )
        if not rows:
            return None
        rows.sort(key=lambda r: 0 if r.source == "manual" else 1)
        row = rows[0]
        row.hits = (row.hits or 0) + 1
        db.commit()
        return str(row.guidance)
    except Exception:
        return None
    finally:
        db.close()


def store(
    check_id: str, stack: str, guidance: str, *,
    source: str = "ai", model: Optional[str] = None,
) -> bool:
    """Upsert guidance for a pair. Returns False if it failed validation."""
    cleaned = _clean(guidance)
    if cleaned is None:
        return False
    db = SessionLocal()
    try:
        row = (
            db.query(PromptKB)
            .filter(PromptKB.check_id == check_id, PromptKB.stack == stack,
                    PromptKB.source == source)
            .first()
        )
        now = datetime.now(timezone.utc)
        if row is None:
            db.add(PromptKB(check_id=check_id, stack=stack, guidance=cleaned,
                            source=source, model=model, created_at=now,
                            updated_at=now))
        else:
            row.guidance, row.model, row.updated_at = cleaned, model, now
        db.commit()
        return True
    except Exception:
        return False
    finally:
        db.close()


def entries(limit: int = 500) -> List[Dict[str, Any]]:
    """List the KB for inspection/editing in the UI."""
    db = SessionLocal()
    try:
        rows = (
            db.query(PromptKB)
            .order_by(PromptKB.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [{
            "id": r.id, "check_id": r.check_id, "stack": r.stack,
            "guidance": r.guidance, "source": r.source, "model": r.model,
            "hits": r.hits or 0,
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        } for r in rows]
    except Exception:
        return []
    finally:
        db.close()


def stats() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        rows = db.query(PromptKB).all()
        return {
            "total": len(rows),
            "manual": sum(1 for r in rows if r.source == "manual"),
            "ai": sum(1 for r in rows if r.source != "manual"),
            "hits": sum((r.hits or 0) for r in rows),
            "stacks": sorted({r.stack for r in rows}),
        }
    except Exception:
        return {"total": 0, "manual": 0, "ai": 0, "hits": 0, "stacks": []}
    finally:
        db.close()


def delete(entry_id: int) -> bool:
    db = SessionLocal()
    try:
        row = db.query(PromptKB).filter(PromptKB.id == entry_id).first()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
    except Exception:
        return False
    finally:
        db.close()


_ENRICH_PROMPT = """You are advising a coding agent that will fix a technical SEO \
issue on a website.

Platform: {stack_label}
Issue: {title}
Why it matters: {why}

Write ONE short block of implementation guidance (3-6 sentences, max 200 words) \
that tells the agent specifically HOW to fix this on {stack_label}: which file, \
hook, template, config key or admin setting to change, and any platform-specific \
pitfall (e.g. a setting that a plugin or framework route would override).

Rules:
- Be concrete about file paths and API names for {stack_label}.
- Do NOT include shell commands that delete, drop, truncate or force-push.
- Do NOT restate why the issue matters; only how to fix it.
- Output plain prose. No headings, no preamble, no markdown fences."""


_ENRICH_SYSTEM = (
    "You write terse, concrete implementation guidance for automated coding "
    "agents. You never suggest destructive commands."
)


def enrich(
    check_id: str,
    stack: str,
    stack_label: str,
    title: str,
    why: str = "",
    cfg: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Generate guidance for a pair via the configured AI provider and cache it.

    `cfg` is passed in by the caller (the web layer owns provider settings) so
    this module stays independent of the API and remains unit-testable.

    Returns None whenever AI is unavailable, declines, or produces something
    that fails validation — the caller then keeps the deterministic template.
    """
    cached = lookup(check_id, stack)
    if cached:
        return cached
    if not cfg:
        return None
    try:
        from sentinelseo.ai.provider import ai_complete, is_configured
    except Exception:
        return None
    if not is_configured(cfg):
        return None
    try:
        text = ai_complete(
            cfg,
            _ENRICH_SYSTEM,
            _ENRICH_PROMPT.format(
                stack_label=stack_label, title=title, why=why or "(not stated)"),
            max_tokens=320,
        )
    except Exception:
        return None
    cleaned = _clean(text or "")
    if cleaned is None:
        return None
    store(check_id, stack, cleaned, source="ai", model=str(cfg.get("model") or ""))
    return cleaned
