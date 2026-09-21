from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class AuditFinding:
    field: str
    severity: Severity
    message: str


@dataclass(frozen=True)
class NotificationPlan:
    name: str
    environment: str
    trigger: str
    audience: str
    exclusions: tuple[str, ...]
    deep_link: str
    quiet_hours: str
    frequency_cap: str
    success_metric: str
    failure_metric: str
    owner: str
    consent_basis: str
    payload_sample: str = ""


_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|device[_-]?token|player[_-]?id)\\s*[:=]\\s*\\S+"
)
_REQUIRED_STRING_FIELDS = (
    "name",
    "environment",
    "trigger",
    "audience",
    "deep_link",
    "quiet_hours",
    "frequency_cap",
    "success_metric",
    "failure_metric",
    "owner",
    "consent_basis",
)
_ALLOWED_FIELDS = {*_REQUIRED_STRING_FIELDS, "exclusions", "payload_sample"}


def validate_plan(plan: NotificationPlan) -> tuple[AuditFinding, ...]:
    """Validate an audit matrix row without contacting or changing a provider."""
    findings: list[AuditFinding] = []
    required = {
        "name": plan.name,
        "environment": plan.environment,
        "trigger": plan.trigger,
        "audience": plan.audience,
        "deep_link": plan.deep_link,
        "quiet_hours": plan.quiet_hours,
        "frequency_cap": plan.frequency_cap,
        "success_metric": plan.success_metric,
        "failure_metric": plan.failure_metric,
        "owner": plan.owner,
        "consent_basis": plan.consent_basis,
    }
    for field, value in required.items():
        if not value.strip():
            findings.append(AuditFinding(field, Severity.ERROR, "required field is blank"))

    environment = plan.environment.strip().lower()
    if environment not in {"test", "staging", "production"}:
        findings.append(
            AuditFinding(
                "environment",
                Severity.ERROR,
                "must be test, staging, or production",
            )
        )

    normalized_exclusions = {value.strip().lower() for value in plan.exclusions}
    if "opted_out" not in normalized_exclusions:
        findings.append(
            AuditFinding(
                "exclusions",
                Severity.ERROR,
                "must suppress opted-out recipients",
            )
        )
    if "already_completed" not in normalized_exclusions:
        findings.append(
            AuditFinding(
                "exclusions",
                Severity.WARNING,
                "consider suppressing users who already completed the target action",
            )
        )

    if plan.deep_link and not (
        plan.deep_link.startswith("https://") or plan.deep_link.startswith("app://")
    ):
        findings.append(
            AuditFinding(
                "deep_link",
                Severity.ERROR,
                "must use an explicit https:// or app:// destination",
            )
        )

    if plan.payload_sample and _SECRET_PATTERN.search(plan.payload_sample):
        findings.append(
            AuditFinding(
                "payload_sample",
                Severity.ERROR,
                "contains a credential or device identifier pattern; redact before delivery",
            )
        )

    if plan.success_metric.strip().lower() in {"opens", "open rate"}:
        findings.append(
            AuditFinding(
                "success_metric",
                Severity.WARNING,
                "open activity alone is not a downstream outcome",
            )
        )

    return tuple(findings)


def is_release_ready(plan: NotificationPlan) -> bool:
    return not any(
        finding.severity is Severity.ERROR for finding in validate_plan(plan)
    )


def plan_from_mapping(value: Any) -> NotificationPlan:
    """Parse one strict JSON object without coercing malformed values."""
    if not isinstance(value, dict):
        raise ValueError("audit file must contain a JSON object")

    unknown = sorted(set(value) - _ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(unknown)}")

    missing = sorted(_ALLOWED_FIELDS - {"payload_sample"} - set(value))
    if missing:
        raise ValueError(f"missing field(s): {', '.join(missing)}")

    for field in _REQUIRED_STRING_FIELDS:
        if not isinstance(value[field], str):
            raise ValueError(f"{field} must be a string")

    payload_sample = value.get("payload_sample", "")
    if not isinstance(payload_sample, str):
        raise ValueError("payload_sample must be a string")

    exclusions = value["exclusions"]
    if not isinstance(exclusions, list) or not all(
        isinstance(item, str) for item in exclusions
    ):
        raise ValueError("exclusions must be an array of strings")

    return NotificationPlan(
        **{field: value[field] for field in _REQUIRED_STRING_FIELDS},
        exclusions=tuple(exclusions),
        payload_sample=payload_sample,
    )


def _finding_dict(finding: AuditFinding) -> dict[str, str]:
    return {
        "field": finding.field,
        "severity": finding.severity.value,
        "message": finding.message,
    }


def _render_result(
    findings: tuple[AuditFinding, ...], output_format: str
) -> str:
    ready = not any(item.severity is Severity.ERROR for item in findings)
    if output_format == "json":
        return json.dumps(
            {
                "release_ready": ready,
                "findings": [_finding_dict(item) for item in findings],
            },
            indent=2,
            sort_keys=True,
        )

    lines = [f"release_ready: {'yes' if ready else 'no'}"]
    lines.extend(
        f"{item.severity.value}: {item.field}: {item.message}" for item in findings
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one redacted lifecycle-notification audit JSON file."
    )
    parser.add_argument("audit_file", help="path to the redacted audit JSON object")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="output_format",
        help="output format (default: text)",
    )
    args = parser.parse_args(argv)

    try:
        raw = Path(args.audit_file).read_text(encoding="utf-8")
        plan = plan_from_mapping(json.loads(raw))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if args.output_format == "json":
            print(
                json.dumps(
                    {
                        "release_ready": False,
                        "findings": [
                            {
                                "field": "audit_file",
                                "severity": "error",
                                "message": str(exc),
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
        else:
            print(f"error: audit_file: {exc}", file=sys.stderr)
        return 2

    findings = validate_plan(plan)
    print(_render_result(findings, args.output_format))
    return 0 if is_release_ready(plan) else 1


if __name__ == "__main__":
    raise SystemExit(main())
