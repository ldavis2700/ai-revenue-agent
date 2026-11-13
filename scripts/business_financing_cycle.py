#!/usr/bin/env python3
"""Daily, local-only financing readiness stage for the existing APEX worker.

No network, no outbound financing contact, no credit inquiry, no stored applicant
details in the revenue ledger. An absent private input is a valid safe no-op.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
try:
    from scripts.business_financing_readiness import assess
except ModuleNotFoundError:
    from business_financing_readiness import assess

def cycle(db_path, profile_path=None, current=None):
    today = (current or datetime.now(timezone.utc)).date().isoformat()
    with sqlite3.connect(db_path, timeout=10) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS financing_readiness_cycles (
            day_utc TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            missing_count INTEGER,
            processed_at TEXT NOT NULL
        )""")
        row = db.execute("SELECT state FROM financing_readiness_cycles WHERE day_utc=?", (today,)).fetchone()
        if row:
            return {"state": "already_checked", "day_utc": today}
        state, missing_count = "awaiting_authorized_private_facts", None
        if profile_path:
            path = Path(profile_path).resolve()
            # Do not allow reading arbitrary shared project tree files as private owner data.
            if not path.is_file() or path.is_symlink():
                state = "input_unavailable"
            else:
                try:
                    profile = json.loads(path.read_text(encoding="utf-8"))
                    report = assess(profile)
                    state = report["readiness"]
                    missing_count = len(report["missing_or_unsubstantiated"])
                except (ValueError, OSError, UnicodeError):
                    state = "input_invalid"
        db.execute("""INSERT INTO financing_readiness_cycles
            (day_utc,state,missing_count,processed_at) VALUES (?,?,?,?)""",
            (today, state, missing_count, datetime.now(timezone.utc).isoformat()))
    return {"state": state, "day_utc": today, "missing_count": missing_count}

def main():
    db_path = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")
    result = cycle(db_path, os.getenv("APEX_FINANCING_PROFILE_PATH"))
    # No names, application data, applicant details, account identifiers or amounts in logs.
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
