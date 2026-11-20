"""Safety-first continuous engineering task controller.

Standard-library only. Starts in DRY RUN, keeps durable SQLite tasks, and never
uses production credentials, APIs, payments or deployment commands. An external,
separately reviewed worker must be added before any code-modifying execution.
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

TASKS = (
    ("HAEVEN", "Review current-release PR #89 and CI issue #86; verify test evidence", 1),
    ("HAEVEN", "Review isolated Emergent exit PR #90 and verified backup prerequisites", 1),
    ("APEX", "Inspect legitimate revenue pipeline and verification evidence; no spending", 2),
    ("RMC CLASSICS", "Review gameplay/CI release blockers and Emergent dependencies", 3),
)


def database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        app TEXT NOT NULL, description TEXT NOT NULL, priority INTEGER NOT NULL,
        last_checked TEXT, attempts INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (app, description))""")
    db.execute("""CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL,
        app TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL)""")
    db.executemany(
        "INSERT OR IGNORE INTO jobs (app, description, priority) VALUES (?, ?, ?)",
        TASKS,
    )
    db.commit()
    return db


def cycle(db):
    """Produce a durable non-mutating review queue, not a false execution claim."""
    if os.getenv("CONTROLLER_EXECUTE", "").lower() in ("1", "true", "yes"):
        raise RuntimeError("Execution is disabled; requires a separate reviewed implementation")
    now = datetime.now(timezone.utc).isoformat()
    rows = db.execute(
        "SELECT app, description, priority FROM jobs ORDER BY priority, COALESCE(last_checked, ''), app"
    ).fetchall()
    for app, description, priority in rows:
        db.execute("UPDATE jobs SET last_checked=?, attempts=attempts+1 WHERE app=? AND description=?",
                   (now, app, description))
        db.execute("INSERT INTO observations (checked_at, app, description, status) VALUES (?, ?, ?, ?)",
                   (now, app, description, "queued_for_read_only_review"))
    db.commit()
    return {"mode": "dry_run", "checked_at": now, "jobs_queued": len(rows),
            "priority_apps": ["HAEVEN", "APEX", "RMC CLASSICS"],
            "production_mutations": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="./runtime/engineering-queue.sqlite3")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()
    if args.interval < 3600:
        parser.error("Minimum interval is 3600 seconds")
    db = database(args.db)
    try:
        while True:
            print(json.dumps(cycle(db), sort_keys=True), flush=True)
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        db.close()


if __name__ == "__main__":
    main()
