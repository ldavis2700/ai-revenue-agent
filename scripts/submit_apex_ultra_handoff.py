#!/usr/bin/env python3
"""Submit one explicitly enabled APEX business case to APEX ULTRA."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apex_ultra_adapter import HandoffError, submit_handoff


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-case-id", required=True)
    parser.add_argument("--project", required=True,
                        choices=["HAEVEN", "APEX", "RMC_CLASSICS"])
    parser.add_argument("--goal", required=True)
    parser.add_argument("--capability", action="append", required=True,
                        choices=["plan", "code_change",
                                 "preview_verification"])
    parser.add_argument("--idempotency-key")
    parser.add_argument(
        "--receipt-db",
        default=os.getenv("APEX_HANDOFF_DB", os.getenv("REVENUE_DB_PATH", "")))
    args = parser.parse_args()
    try:
        result = submit_handoff(
            business_case_id=args.business_case_id,
            project=args.project,
            goal=args.goal,
            requested_capabilities=args.capability,
            idempotency_key=args.idempotency_key,
            receipt_db_path=args.receipt_db or None)
    except HandoffError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)},
                         sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
