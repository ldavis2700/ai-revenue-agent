#!/usr/bin/env python3
"""Local owner/operator controls for APEX revenue worker.

This is a LOCAL CLI, not an internet-exposed administrative API. Access must
be limited to authorized operators by the host's OS and deployment permissions.
A pause is persistent across worker restarts, and the kill switch always wins.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import sys

DEFAULT_DB = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _paths(db_path):
    db = Path(db_path).expanduser().resolve()
    return db, Path(str(db) + ".pause"), Path(str(db) + ".owner_audit.jsonl")


def _audit(path, action, outcome):
    # Keep customer data and credentials out of owner-control audit logs.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(json.dumps({"at": _now(), "action": action,
                                     "outcome": outcome}, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        pass


def execute(action, db_path=DEFAULT_DB):
    db, pause, audit = _paths(db_path)
    if action == "status":
        kill = os.getenv("REVENUE_AGENT_KILL_SWITCH", "false").lower() == "true"
        info = {"paused_by_owner": pause.exists(),
                "kill_switch_active": kill, "dispatch_allowed": not (kill or pause.exists())}
        try:
            # Read-only status: never create or initialize a database.
            from revenue_worker import status
            info["worker"] = status(str(db))
        except (sqlite3.Error, FileNotFoundError, ImportError, ValueError):
            info["worker"] = {"state": "unavailable", "healthy": False}
        return info
    if action not in ("pause", "resume"):
        raise ValueError("unsupported owner action")
    # Parent directory should already exist and be managed by the operator.
    if not db.parent.is_dir():
        raise FileNotFoundError("worker database directory does not exist")
    if action == "pause":
        fd = os.open(pause, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
        outcome = "paused"
    else:
        try:
            pause.unlink()
            outcome = "resumed" if os.getenv("REVENUE_AGENT_KILL_SWITCH", "false").lower() != "true" else "owner_pause_removed_kill_switch_active"
        except FileNotFoundError:
            outcome = "already_unpaused"
    _audit(audit, action, outcome)
    return {"action": action, "outcome": outcome, "paused_by_owner": pause.exists(),
            "kill_switch_active": os.getenv("REVENUE_AGENT_KILL_SWITCH", "false").lower() == "true"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "pause", "resume"))
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.action, args.db), sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"error": type(error).__name__, "action": args.action}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
