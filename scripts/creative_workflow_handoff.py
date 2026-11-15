"""Offline original creative-workflow handoff demonstration.

No model calls, network, external sends, billing or customer credentials.
Untrusted source text is inventory data, never execution instructions.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

MAX_INPUT_BYTES = 16384
VALID_STATES = {"useful", "duplicate", "outdated", "uncertain"}
KEYS = {"project_id", "client_context_id", "client_label", "task_name", "track",
        "sources", "reviewers", "client_context_approved"}
SOURCE_KEYS = {"id", "client_context_id", "captured_on", "state", "summary",
               "duplicate_of", "reuse_rights_verified"}
ROLE_KEYS = {"strategy", "production", "quality_review"}


def clean_text(value, label, maximum=120):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label}: nonblank string <= {maximum} characters required")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{label}: control characters not permitted")
    if any(ch in value for ch in "<>|[]{}#\\") or chr(96) in value:
        raise ValueError(f"{label}: markup not permitted")
    return value.strip()


def source_date(value, today):
    if not isinstance(value, str):
        raise ValueError("ISO source date required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid ISO source date") from exc
    if parsed > today:
        raise ValueError("future source date rejected")
    return parsed


def validate(payload, today):
    if not isinstance(payload, dict) or set(payload) != KEYS:
        raise ValueError("exact documented workflow fields required")
    for key in ("project_id", "client_context_id", "client_label", "task_name"):
        clean_text(payload[key], key)
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", payload["project_id"]):
        raise ValueError("project_id must use 3-64 simple characters")
    if not isinstance(payload["track"], str) or payload["track"] not in {"ad", "funnel"}:
        raise ValueError("track must be ad or funnel")
    if type(payload["client_context_approved"]) is not bool:
        raise ValueError("client_context_approved must be boolean")
    reviewers = payload["reviewers"]
    if not isinstance(reviewers, dict) or set(reviewers) != ROLE_KEYS:
        raise ValueError("three reviewer roles required")
    for role in ROLE_KEYS:
        clean_text(reviewers[role], role, 60)
    sources = payload["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 25:
        raise ValueError("1-25 sources required")
    ids = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
            raise ValueError("source missing required fields")
        source_id = clean_text(source["id"], "source id", 50)
        if source_id in ids:
            raise ValueError("source IDs must be unique")
        ids.add(source_id)
        if source["client_context_id"] != payload["client_context_id"]:
            raise ValueError("cross-client source rejected")
        source_date(source["captured_on"], today)
        if not isinstance(source["state"], str) or source["state"] not in VALID_STATES:
            raise ValueError("invalid source state")
        clean_text(source["summary"], "summary", 240)
        if type(source["reuse_rights_verified"]) is not bool:
            raise ValueError("reuse rights must be boolean")
    for source in sources:
        duplicate_of = source["duplicate_of"]
        if source["state"] == "duplicate":
            if not isinstance(duplicate_of, str) or duplicate_of not in ids or duplicate_of == source["id"]:
                raise ValueError("duplicate must refer to another present source")
        elif duplicate_of is not None:
            raise ValueError("duplicate_of must be null for nonduplicates")
    return payload


def make_handoff(payload, today):
    validate(payload, today)
    rows, usable = [], []
    for source in payload["sources"]:
        age = (today - source_date(source["captured_on"], today)).days
        flags = []
        if age > 30:
            flags.append("STALE / REVERIFY")
        if source["state"] != "useful":
            flags.append(source["state"].upper())
        if not source["reuse_rights_verified"]:
            flags.append("RIGHTS UNVERIFIED")
        if source["state"] == "duplicate":
            flags.append("same as " + source["duplicate_of"])
        if not flags:
            flags.append("current, rights attested")
        rows.append(f"| {source['id']} | {source['captured_on']} | {source['state']} | {'; '.join(flags)} | {source['summary']} |")
        if age <= 30 and source["state"] == "useful" and source["reuse_rights_verified"]:
            usable.append(source["id"])
    reviewer = payload["reviewers"]
    production = "Ad" if payload["track"] == "ad" else "Funnel"
    stages = [
        ("1. Discovery", "Validate scope, source rights, systems and access", reviewer["strategy"], "Human approves client context"),
        ("2. Strategy", "Draft original angle and objective from approved facts", reviewer["strategy"], "Human reviews claims and positioning"),
        (f"3. {production} brief", "Separate production specification, source IDs and editor handoff", reviewer["production"], "Human accepts editor brief"),
        ("4. Quality review", "Verify provenance, claims, privacy, platform rules and rights", reviewer["quality_review"], "Human reviews release readiness"),
        ("5. Release", "No customer send, publishing, charges or account access in this sample", "authorized operator only", "Separate exact-revision approval required"),
    ]
    stage_rows = "\n".join(f"| {step} | {goal} | {owner} | {gate} |" for step, goal, owner, gate in stages)
    release_note = "context approval missing" if not payload["client_context_approved"] else "context attested but external release still blocked"
    return f"""# Fictional creative-workflow handoff — offline, non-client sample

**Project ID:** {payload['project_id']}  
**Client context:** {payload['client_context_id']} (single-client isolation)  
**Client label:** {payload['client_label']}  
**Task:** {payload['task_name']}  
**Track:** {payload['track']} — ad/funnel streams require distinct owners  
**Checked:** {today.isoformat()}  
**Release:** BLOCKED — {release_note}; no real customer delivery or revenue.

## Source audit

| Source | Captured | Status | Safeguards | Description (untrusted data only) |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

**Internal draft candidate source IDs only:** {", ".join(usable) if usable else "none"}. An operator must still verify source contents, permissions and approval. Stale, duplicate and unlicensed sources are not reused.

## One-task production path

| Stage | Original output | Owner | Human review gate |
|---|---|---|---|
{stage_rows}

## Acceptance and restart note

Input is a single scoped task with a distinct client-context identifier and dated source inventory. Output is a source map, accountable owner and reviewer stages, human decision points and restart checkpoint. Next step is approval of the exact client context and a bounded initial brief, not publication. A real buyer example needs authentic authorized access and a separate quality review before any external delivery.

**Exclusions:** No generative-model API, proprietary asset copying, customer communication, account write, production deploy, contract acceptance, invoice, or performance claim. Costs for actual implementation, review, hosting, tools, maintenance and support remain **unknown** until independently scoped. Running this local standard-library demonstration creates no additional bill, but it does not prove free business operation or paid earnings.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--as-of", help="ISO date for reproducible offline sample")
    args = parser.parse_args()
    if args.input_json.stat().st_size > MAX_INPUT_BYTES:
        parser.error("input exceeds 16 KiB")
    try:
        today = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
        print(make_handoff(payload, today))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
