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
import stat
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
        # A missing or rejected private profile must not block a newly authorized,
        # corrected profile until tomorrow. Never rerun an already evaluated valid one.
        if row and (not profile_path or row[0] not in (
                "awaiting_authorized_private_facts", "input_unavailable", "input_invalid")):
            return {"state": "already_checked", "day_utc": today}
        state, missing_count = "awaiting_authorized_private_facts", None
        if profile_path:
            # Accept only an explicit, regular file outside the repository.
            # Validate the original path before following it: resolving first
            # would hide a symlink (including one in a parent directory).
            path = Path(profile_path)
            try:
                resolved = path.resolve(strict=True)
                repo_root = Path(__file__).resolve().parents[1]
                metadata = resolved.stat()
                # Private applicant facts must not be accessible to the group or
                # world. Refuse insecure input rather than logging its contents.
                owner_only = (
                    stat.S_ISREG(metadata.st_mode)
                    and (metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO)) == 0
                    and hasattr(os, "getuid")
                    and metadata.st_uid == os.getuid()
                )
                allowed = (
                    owner_only
                    and path.is_absolute()
                    and path.absolute() == resolved
                    and resolved.is_file()
                    and repo_root != resolved
                    and repo_root not in resolved.parents
                )
            except (OSError, ValueError, RuntimeError):
                allowed = False
            if not allowed:
                state = "input_unavailable"
            else:
                try:
                    profile = json.loads(path.read_text(encoding="utf-8"))
                    report = assess(profile)
                    state = report["readiness"]
                    missing_count = len(report["missing_or_unsubstantiated"])
                except (ValueError, OSError, UnicodeError):
                    state = "input_invalid"
        processed_at = datetime.now(timezone.utc).isoformat()
        if row:
            db.execute("""UPDATE financing_readiness_cycles
                SET state=?, missing_count=?, processed_at=? WHERE day_utc=?""",
                (state, missing_count, processed_at, today))
        else:
            db.execute("""INSERT INTO financing_readiness_cycles
                (day_utc,state,missing_count,processed_at) VALUES (?,?,?,?)""",
                (today, state, missing_count, processed_at))
    return {"state": state, "day_utc": today, "missing_count": missing_count}

def main():
    db_path = os.getenv("REVENUE_DB_PATH", "/files/data/revenue_agent.db")
    result = cycle(db_path, os.getenv("APEX_FINANCING_PROFILE_PATH"))
    # No names, application data, applicant details, account identifiers or amounts in logs.
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
