#!/usr/bin/env python3
"""Read-only offline integrity audit for the human-reviewed $100 response pack.

An integrity pass is NOT buyer acceptance, substantive fact review, permission
for contact/delivery, Stripe settlement, or revenue. Never print client data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import stat
from pathlib import Path

ARTIFACTS = ("response-pack.html", "response-use-guide.md", "inquiry-tracker.csv")
EXPECTED = frozenset((*ARTIFACTS, "manifest.json"))
TRACKER_COLUMNS = (
    "inquiry_reference", "inquiry_type", "status", "contact_permission_verified",
    "opted_out", "next_action", "next_action_due", "human_owner",
    "template_used", "response_sent_at",
)
MAX_BYTES = {"response-pack.html": 200000, "response-use-guide.md": 20000,
             "inquiry-tracker.csv": 5000, "manifest.json": 16000}
HASH = re.compile(r"[a-f0-9]{64}\Z")


class PackAuditError(ValueError):
    """Failed verification, without exposing buyer data."""


def audit_pack(directory: Path) -> dict:
    """Check an immutable draft against the original builder contract, read-only."""
    path = Path(directory)
    if path.is_symlink() or not path.is_dir():
        raise PackAuditError("Private pack directory is missing or is a symlink")
    if (stat.S_IMODE(path.stat().st_mode) & 0o077) != 0:
        raise PackAuditError("Pack directory must not grant group/other access")
    if {entry.name for entry in path.iterdir()} != EXPECTED:
        raise PackAuditError("Pack file set does not match the builder contract")
    contents = {}
    for filename in EXPECTED:
        entry = path / filename
        if entry.is_symlink() or not entry.is_file():
            raise PackAuditError("Missing or unsafe regular file: " + filename)
        if entry.stat().st_size > MAX_BYTES[filename]:
            raise PackAuditError("Oversized file: " + filename)
        contents[filename] = entry.read_bytes()
    try:
        manifest = json.loads(contents["manifest.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackAuditError("Manifest is not valid JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != {
            "status", "message_count", "messages_sent", "delivery_verified",
            "buyer_acceptance_verified", "payment_verified", "files"}:
        raise PackAuditError("Unexpected manifest structure")
    if (manifest["status"] != "draft_requires_business_review"
            or type(manifest["message_count"]) is not int or manifest["message_count"] != 14
            or type(manifest["messages_sent"]) is not int or manifest["messages_sent"] != 0
            or any(manifest[key] is not False for key in (
                "delivery_verified", "buyer_acceptance_verified", "payment_verified"))):
        raise PackAuditError("Manifest must remain an unsent, unaccepted, unpaid draft")
    hashes = manifest["files"]
    if not isinstance(hashes, dict) or set(hashes) != set(ARTIFACTS):
        raise PackAuditError("Missing or unexpected content digests")
    for filename in ARTIFACTS:
        digest = hashes[filename]
        if not isinstance(digest, str) or not HASH.fullmatch(digest):
            raise PackAuditError("Invalid digest: " + filename)
        if hashlib.sha256(contents[filename]).hexdigest() != digest:
            raise PackAuditError("Content digest mismatch: " + filename)
    try:
        html = contents["response-pack.html"].decode("utf-8")
        guide = contents["response-use-guide.md"].decode("utf-8")
        tracker = contents["inquiry-tracker.csv"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackAuditError("Response pack must use UTF-8") from exc
    if (html.count("<strong>Option ") != 14
            or html.count("<h2>") != 8  # business facts plus seven inquiry categories
            or "DRAFT — business review required" not in html
            or "default-src 'none'" not in html):
        raise PackAuditError("Response copy/markup is incomplete")
    if "## Acceptance checklist" not in guide or "HOLD" not in guide:
        raise PackAuditError("Human-review guidance is missing")
    try:
        rows = list(csv.reader(io.StringIO(tracker)))
    except csv.Error as exc:
        raise PackAuditError("Invalid tracker CSV") from exc
    if rows != [list(TRACKER_COLUMNS)]:
        raise PackAuditError("Tracker must have its expected header and no customer rows")
    return {
        "integrity_verified": True,
        "artifact_count": len(ARTIFACTS),
        "draft_reply_count": 14,
        "substantive_buyer_fact_review_verified": False,
        "buyer_acceptance_verified": False,
        "delivery_authorized": False,
        "payment_or_settlement_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True,
                        help="Existing private pack directory; read-only")
    args = parser.parse_args()
    try:
        print(json.dumps(audit_pack(args.pack), sort_keys=True))
    except (PackAuditError, OSError) as exc:
        # Never include a client-provided path or document content in an error.
        reason = str(exc) if isinstance(exc, PackAuditError) else "Cannot read pack files"
        print(json.dumps({"integrity_verified": False, "error": reason}, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
