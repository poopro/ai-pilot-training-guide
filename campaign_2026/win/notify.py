"""Notification bus. Chat-first, email best-effort, never silently drops.

Channels, in order:
  1. append-only  NOTICES/events.jsonl      (always)
  2. NOTICES/<event_id>.md                 (always, human readable)
  3. needs_you.json                         (only when a human action is required)
  4. Gmail via Hermes MCP                   (only if already authenticated; never blocks)

Gmail is currently parked (no cached OAuth token), so channel 4 degrades to a
recorded 'email_unavailable' instead of failing or pretending to have sent.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTICES = ROOT / "NOTICES"
NOTICES.mkdir(exist_ok=True)
LEDGER = NOTICES / "events.jsonl"
NEEDS_YOU = ROOT / "needs_you.json"

# Only these classes are allowed to page a human. Everything else is logged only.
PAGE_CLASSES = {
    "blocker",            # cannot proceed without a decision
    "user_action",        # a login / document / hardware step only they can do
    "deadline",           # a hard external deadline
    "backstop",           # a job exceeded the age backstop
    "win",                # a gate passed and changes the deployment decision
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _sent_ids() -> set:
    if not LEDGER.exists():
        return set()
    out = set()
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.add(json.loads(line)["event_id"])
        except Exception:
            continue
    return out


def _email_available() -> bool:
    cache = Path(os.environ.get("USERPROFILE", ".")) / ".hermes" / "gmail"
    return cache.exists()


def _try_email(subject: str, body: str) -> str:
    """Returns a delivery status string. Never raises."""
    if not _email_available():
        return "email_unavailable"
    try:
        p = subprocess.run(["hermes", "mcp", "call", "gmail", "send_email",
                            "--subject", subject, "--body", body],
                           capture_output=True, text=True, timeout=60)
        return "sent" if p.returncode == 0 else f"email_failed_rc{p.returncode}"
    except Exception as e:  # noqa: BLE001
        return f"email_error:{type(e).__name__}"


def emit(event_id: str, status: str, gate: str, message: str, *,
         cls: str = "info", evidence: str = "", report: str = "",
         eli5: list | None = None) -> dict:
    """Record one event. Deduplicated on event_id."""
    now = datetime.now(timezone.utc).isoformat()
    body = f"{message}\n\nevent: {event_id}\nstatus: {status}\ngate: {gate}"
    if eli5:
        body += "\n\n需要你做的事（照做）：\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(eli5, 1))
    event = {
        "event_id": event_id, "status": status, "gate": gate, "class": cls,
        "message": message, "evidence": evidence, "report": report,
        "body_sha": _sha(body), "utc": now,
        "local": datetime.now().isoformat(timespec="seconds"),
        "delivery": {"chat": True, "file": True},
    }
    if event_id in _sent_ids():
        event["duplicate_suppressed"] = True
        return event

    if cls in PAGE_CLASSES:
        event["delivery"]["email"] = _try_email(f"【AI飛行員】{message[:80]}", body)

    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    (NOTICES / f"{event_id}.md").write_text(
        f"# {event_id}\n\n- status: {status}\n- gate: {gate}\n- class: {cls}\n"
        f"- utc: {now}\n- report: {report or '(none)'}\n\n{message}\n"
        + ("\n## 需要你做的事\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(eli5, 1))
           if eli5 else ""), encoding="utf-8")

    if cls in PAGE_CLASSES and eli5:
        cur = json.loads(NEEDS_YOU.read_text(encoding="utf-8")) if NEEDS_YOU.exists() else {}
        cur[event_id] = {"message": message, "eli5": eli5, "raised_utc": now,
                         "email": event["delivery"].get("email"), "status": "open"}
        NEEDS_YOU.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")

    return event


def resolve(event_id: str) -> bool:
    """Mark a paged item as handled."""
    if not NEEDS_YOU.exists():
        return False
    cur = json.loads(NEEDS_YOU.read_text(encoding="utf-8"))
    if event_id not in cur:
        return False
    cur[event_id]["status"] = "resolved"
    cur[event_id]["resolved_utc"] = datetime.now(timezone.utc).isoformat()
    NEEDS_YOU.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def open_items() -> list:
    if not NEEDS_YOU.exists():
        return []
    d = json.loads(NEEDS_YOU.read_text(encoding="utf-8"))
    return [{"event_id": k, **v} for k, v in d.items() if v.get("status") == "open"]


if __name__ == "__main__":
    print(json.dumps({"open": open_items(),
                      "email_available": _email_available(),
                      "ledger": str(LEDGER)}, ensure_ascii=False, indent=2))
