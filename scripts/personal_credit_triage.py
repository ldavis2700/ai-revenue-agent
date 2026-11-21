"""Local-only credit monitoring triage. No API keys, network calls, payments or disputes.

Input: a JSON object with account summaries the owner has explicitly authorized
for local processing. Never persist inputs or output personally identifying data.
This is decision support, not a score predictor or a debt-collection service.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path


def triage(report: dict) -> dict:
    """Return non-identifying review recommendations and approval gates."""
    if not isinstance(report, dict):
        raise ValueError("Expected JSON object")
    findings = []
    for index, account in enumerate(report.get("accounts", [])):
        if not isinstance(account, dict):
            continue
        label = f"account_{index + 1}"  # intentionally omit creditor/account identity
        status = str(account.get("status") or "").lower()
        past_due = account.get("past_due_amount")
        if isinstance(past_due, (int, float)) and past_due > 0:
            findings.append({"item": label, "priority": "urgent",
                "action": "Verify the reported past-due amount and payment deadline with the creditor; arrange an affordable payment only with owner approval.",
                "reason": "reported_past_due"})
        balance, limit = account.get("balance"), account.get("credit_limit")
        if (isinstance(balance, (int, float)) and isinstance(limit, (int, float))
                and limit > 0 and "closed" not in status):
            ratio = balance / limit
            if ratio >= .9:
                findings.append({"item": label, "priority": "high",
                    "action": "Review high individual-card utilization and consider an affordable balance reduction; no automatic payment.",
                    "reason": "high_individual_utilization"})
        if "charge" in status or account.get("charge_off") is True:
            findings.append({"item": label, "priority": "review",
                "action": "Check charge-off reporting dates, ownership and balances against documentary evidence; dispute only verified inaccuracies with approval.",
                "reason": "charge_off_review"})
    collections = report.get("collections", [])
    if isinstance(collections, list) and collections:
        findings.append({"item": "collections", "priority": "review",
            "action": "Verify each collection's identity, balance, ownership and reporting dates with documentary evidence; do not assume a collection is inaccurate.",
            "reason": "collection_verification", "count": len(collections)})
    return {
        "report_date": str(report.get("report_date") or "unknown"),
        "findings": findings,
        "requires_owner_approval": ["dispute_submission", "payment", "account_application",
                                    "creditor_contact", "data_transfer"],
        "limitations": ["No credit score forecasts or automatic account changes.",
                        "Only owner-supplied, authorized data is analyzed.",
                        "A bureau connection is NOT established by this module."]
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python personal_credit_triage.py /path/to/private-report.json", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(triage(data), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
