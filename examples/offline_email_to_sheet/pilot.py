#!/usr/bin/env python3
"""Offline, synthetic email-to-CSV reliability demonstration. No network operations."""
import argparse
import csv
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HEADERS = ["message_id", "received_at", "sender", "subject", "category", "followup_status"]


def atomic_write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pilot-", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def category(subject):
    lower = subject.casefold()
    if any(word in lower for word in ("appointment", "meeting", "schedule")):
        return "appointment"
    if any(word in lower for word in ("quote", "estimate", "request", "lead")):
        return "lead"
    return "review"


def safe_cell(value):
    if not isinstance(value, str):
        raise ValueError("spreadsheet value must be a string")
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def validate_message(message):
    if not isinstance(message, dict):
        raise ValueError("message must be an object")
    for field in ("id", "received_at", "sender", "subject"):
        if not isinstance(message.get(field), str) or not message[field].strip():
            raise ValueError(f"missing/nonstring {field}")
    if any(char in message["id"] for char in ("\r", "\n", "\x00")) or len(message["id"]) > 180:
        raise ValueError("invalid message id")
    return message


def process(messages, output_dir, inject_failure=False):
    output_dir = Path(output_dir)
    sheet = output_dir / "synthetic_sheet.csv"
    log = output_dir / "execution_log.json"
    rows = []
    appended = []
    try:
        if sheet.exists():
            with sheet.open(newline="", encoding="utf-8") as existing:
                reader = csv.DictReader(existing)
                if reader.fieldnames != HEADERS:
                    raise ValueError("unexpected sheet schema")
                rows = list(reader)
        seen = {row["message_id"] for row in rows}

        if not isinstance(messages, list):
            raise ValueError("input root must be array")
        for raw in messages:
            message = validate_message(raw)
            canonical_id = safe_cell(message["id"])
            if canonical_id in seen:
                continue
            seen.add(canonical_id)
            appended.append({
                "message_id": canonical_id,
                "received_at": safe_cell(message["received_at"]),
                "sender": safe_cell(message["sender"]),
                "subject": safe_cell(message["subject"]),
                "category": category(message["subject"]),
                "followup_status": "APPROVAL_REQUIRED_NO_EXTERNAL_ACTION",
            })
        if inject_failure:
            raise RuntimeError("deliberate synthetic failure: no sheet commit")
        destination = io.StringIO(newline="")
        writer = csv.DictWriter(destination, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows + appended)
        atomic_write(sheet, destination.getvalue())
        report = {
            "state": "success", "new_records": len(appended),
            "skipped_existing_or_repeat": len(messages) - len(appended),
            "total_records": len(rows) + len(appended),
            "external_calls": 0, "send_permission": False,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        report = {
            "state": "failure", "reason": str(exc), "new_records": 0,
            "external_calls": 0, "send_permission": False,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    atomic_write(log, json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--inject-failure", action="store_true")
    args = parser.parse_args()
    result = process(
        json.loads(args.input.read_text(encoding="utf-8")),
        args.output_dir,
        inject_failure=args.inject_failure,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["state"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
