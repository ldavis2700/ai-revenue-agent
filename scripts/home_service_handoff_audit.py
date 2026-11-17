"""Offline, privacy-minimizing handoff gap audit from synthetic/aggregate counts only.

No connector access, customer records, provider writes, cost or revenue estimates.
"""
import argparse
import json
from pathlib import Path

FLOWS = {"inquiry_to_estimate", "estimate_to_job", "job_to_invoice", "invoice_to_followup"}
MAX_CASES = 1_000_000


def analyze(payload):
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "flows"} or type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("expected exact schema_version=1 and flows")
    flows = payload["flows"]
    if not isinstance(flows, list) or not (1 <= len(flows) <= len(FLOWS)):
        raise ValueError("expected 1-4 aggregate workflow records")
    seen = set()
    results = []
    for flow in flows:
        if not isinstance(flow, dict) or set(flow) != {"id", "cases", "late_or_missing_handoffs", "staff_review_minutes"}:
            raise ValueError("unexpected field: aggregate counts only, no identifying details")
        flow_id = flow["id"]
        if not isinstance(flow_id, str) or flow_id not in FLOWS or flow_id in seen:
            raise ValueError("unknown or duplicated workflow id")
        seen.add(flow_id)
        cases, misses, minutes = (flow[k] for k in ("cases", "late_or_missing_handoffs", "staff_review_minutes"))
        if any(type(v) is not int or v < 0 or v > MAX_CASES for v in (cases, misses, minutes)) or misses > cases:
            raise ValueError("counts must be bounded nonnegative integers; missed <= cases")
        results.append({
            "id": flow_id,
            "sampled_cases": cases,
            "observed_late_or_missing": misses,
            "late_or_missing_share_pct": round(100 * misses / cases, 1) if cases else None,
            "observed_staff_review_minutes": minutes,
            "review_priority": "measure_baseline" if not cases else ("investigate" if misses else "monitor"),
        })
    results.sort(key=lambda r: (r["late_or_missing_share_pct"] is None, -(r["late_or_missing_share_pct"] or 0), -r["observed_staff_review_minutes"], r["id"]))
    return {
        "status": "offline_aggregate_observation_only",
        "flows": results,
        "cautions": [
            "Counts are operator-supplied and are not provider-verified.",
            "Do not infer cause, sales leakage, money saved, ROI, or customer satisfaction from these counts.",
            "Any implementation requires real client authorization, scoped systems access, acceptance tests, privacy review, and funded agreement.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Offline home-service handoff gap audit (no customer data)")
    parser.add_argument("--input", required=True, help="JSON file with anonymous aggregate counts only")
    args = parser.parse_args()
    raw = Path(args.input).read_bytes()
    if len(raw) > 100_000:
        parser.error("input too large")
    try:
        result = analyze(json.loads(raw))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
