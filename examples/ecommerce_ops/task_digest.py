#!/usr/bin/env python3
"""Offline, human-reviewed task digest demonstration; never contacts Slack or Notion."""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re

MAX_INPUT_BYTES = 200_000
MAX_TASKS = 200
OWNER = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def safe_text(value):
    """Plain text suitable for review without Slack command/mention injection."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task title must be nonempty text")
    flat = " ".join(value.split())
    return flat[:140].replace("<", "‹").replace(">", "›").replace("&", "＆").replace("@", "＠")


def build_digest(tasks, today):
    """Returns deterministic preview-only team and owner messages, never sends."""
    if not isinstance(today, date) or isinstance(today, type):
        raise ValueError("today must be a date")
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise ValueError("tasks must be a list with at most 200 entries")
    seen = set()
    team, private = [], {}
    for task in tasks:
        if not isinstance(task, dict) or not {"id", "title", "owner", "due_date", "visibility", "status", "priority"} <= task.keys():
            raise ValueError("incomplete task record")
        task_id, owner = task["id"], task["owner"]
        if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", task_id) or task_id in seen:
            raise ValueError("invalid or duplicate task id")
        seen.add(task_id)
        if not isinstance(owner, str) or not OWNER.fullmatch(owner):
            raise ValueError("invalid owner key; use non-PII demo identifiers")
        if task["visibility"] not in ("team", "private") or task["status"] not in ("open", "done") or task["priority"] not in ("normal", "urgent"):
            raise ValueError("invalid task classification")
        try:
            due = date.fromisoformat(task["due_date"])
        except (TypeError, ValueError):
            raise ValueError("invalid ISO due date") from None
        title = safe_text(task["title"])
        if task["status"] == "done" or (due > today + timedelta(days=7) and task["priority"] != "urgent"):
            continue
        flag = "URGENT" if task["priority"] == "urgent" else "DUE"
        line = f"[{flag} {due.isoformat()}] {title} (owner: {owner})"
        if task["visibility"] == "team":
            team.append((due.isoformat(), task_id, line))
        else:
            private.setdefault(owner, []).append((due.isoformat(), task_id, line))
    return {
        "delivery": "preview_only_no_network_or_automatic_send",
        "team_message": "\n".join(x[2] for x in sorted(team)),
        "direct_messages": {owner: "\n".join(x[2] for x in sorted(lines)) for owner, lines in sorted(private.items())},
        "requires_human_review": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--date", required=True, help="ISO YYYY-MM-DD; no current-time guessing")
    args = parser.parse_args()
    if not args.input.is_file() or args.input.stat().st_size > MAX_INPUT_BYTES:
        parser.error("input missing or too large")
    try:
        today = date.fromisoformat(args.date)
        tasks = json.loads(args.input.read_text(encoding="utf-8"))
        report = build_digest(tasks, today)
    except (ValueError, UnicodeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
