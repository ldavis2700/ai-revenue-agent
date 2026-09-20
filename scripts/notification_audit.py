from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


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
    r"(?i)(api[_-]?key|authorization|bearer|device[_-]?token|player[_-]?id)\s*[:=]\s*\S+"
)


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
