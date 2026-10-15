Warning: truncated output (original token count: 72992)
Total output lines: 5803

#!/usr/bin/env python3
"""Normalize, screen, deduplicate, and rank paid-work opportunities.

This module is deliberately an intake boundary, not an application bot.  It may
recommend autonomous submission only when the source explicitly says that
automation is permitted, the authenticated channel is available, and the
opportunity itself carries an affirmative submission authorization.
"""
import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit, urlunsplit


DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_DB_PATH = "/files/data/revenue_agent.db"
MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_APPLICATION_BALANCE_AGE = timedelta(minutes=15)
MAX_SUBMISSION_AUTHORIZATION_AGE = timedelta(minutes=30)
MAX_APPLICATION_SPEND_AUTHORIZATION_AGE = timedelta(minutes=30)
PROHIBITED_CATEGORIES = {
    "adult", "credential_theft", "deceptive_reviews", "fraud", "malware",
    "regulated_financial_advice", "spam", "surveillance",
}
BUYER_STAGE_SCORES = {
    "prospect": 0.0,
    "qualified": 0.15,
    "proposal": 0.30,
    "invitation": 0.55,
    "buyer_reply": 0.55,
    "interview": 0.70,
    "offer": 0.90,
    "contract": 1.0,
}
BUYER_STAGE_PRIORITY = {
    "prospect": 0,
    "qualified": 1,
    "proposal": 2,
    "invitation": 3,
    "buyer_reply": 3,
    "interview": 4,
    "offer": 5,
    "contract": 6,
}
OFFER_PHASES = {
    "diagnostic", "pilot", "implementation", "managed_recurring",
    "outcome_pricing", "vertical_ip", "productized_agent_saas",
}
OFFER_FAMILY_CATALOG_VERSION = "2026-09-26"
OFFER_FAMILY_CATALOG = {
    "lead_intake_qualification_routing_booking": {
        "icp": "Service businesses with material inbound volume, measurable response-to-booking leakage, and authorized CRM/calendar access.",
        "qualification": [
            "inbound_volume_measured",
            "baseline_conversion_known",
            "crm_calendar_access_authorized",
            "human_exception_owner_named"
        ],
        "measurable_value": "Incremental qualified bookings and response-time reduction against an agreed baseline.",
        "decision_rule": {
            "deterministic_default": "Validate, deduplicate, route, schedule, and enforce consent rules.",
            "ai_when": "Unstructured inquiry intent or qualification judgment materially improves routing."
        },
        "delivery_playbook": [
            "map intake sources and consent",
            "establish baseline and acceptance tests",
            "implement routing and booking",
            "add retries audit trail and escalation",
            "run QA and bounded pilot"
        ],
        "qa_checklist": [
            "duplicate suppression",
            "consent and opt-out enforcement",
            "routing accuracy",
            "calendar idempotency",
            "human escalation",
            "outcome attribution"
        ],
        "economics_inputs": [
            "monthly_lead_volume",
            "baseline_booking_rate",
            "booking_value",
            "implementation_hours",
            "monthly_tool_cost",
            "exception_hours"
        ],
        "retention_upsell": [
            "managed monitoring",
            "routing optimization",
            "additional channels",
            "reactivation"
        ],
        "reusable_ip_target": "Consent-aware intake router, qualification eval set, and booking connector bundle.",
        "maturity": "learned"
    },
    "missed_lead_recovery_reactivation": {
        "icp": "Businesses with consented missed or dormant leads, attributable revenue per recovered opportunity, and usable contact history.",
        "qualification": [
            "consented_lead_set_available",
            "suppression_list_current",
            "baseline_recovery_known",
            "attribution_window_defined"
        ],
        "measurable_value": "Verified recovered appointments or revenue from eligible missed and dormant leads.",
        "decision_rule": {
            "deterministic_default": "Apply eligibility, suppression, cadence, stop, and attribution rules.",
            "ai_when": "Personalized classification or response handling improves recovery without weakening consent."
        },
        "delivery_playbook": [
            "validate consent and suppression",
            "define dormant cohort and baseline",
            "launch bounded recovery workflow",
            "stop on reply or opt-out",
            "reconcile attributed outcomes"
        ],
        "qa_checklist": [
            "consent provenance",
            "suppression enforcement",
            "cadence caps",
            "reply stop",
            "duplicate attribution",
            "refund exclusions"
        ],
        "economics_inputs": [
            "eligible_lead_count",
            "baseline_recovery_rate",
            "recovered_value",
            "message_cost",
            "human_exception_hours",
            "refund_rate"
        ],
        "retention_upsell": [
            "continuous missed-lead capture",
            "cohort optimization",
            "channel expansion",
            "managed attribution"
        ],
        "reusable_ip_target": "Suppression-safe recovery engine, cohort templates, and attribution receipts.",
        "maturity": "learned"
    },
    "crm_sales_ops_automation": {
        "icp": "Sales teams with repetitive CRM hygiene, routing, follow-up, and reporting work across documented stages.",
        "qualification": [
            "crm_access_authorized",
            "pipeline_stages_documented",
            "field_ownership_defined",
            "baseline_admin_hours_known"
        ],
        "measurable_value": "Reduced CRM administration time, faster follow-up, and improved stage/data completeness.",
        "decision_rule": {
            "deterministic_default": "Synchronize fields, enforce stages, deduplicate, assign, and trigger approved tasks.",
            "ai_when": "Notes, emails, or call summaries require structured extraction or judgment."
        },
        "delivery_playbook": [
            "map schema and ownership",
            "baseline errors and labor",
            "build deterministic sync rules",
            "add bounded AI extraction",
            "reconcile and monitor"
        ],
        "qa_checklist": [
            "schema validation",
            "idempotent updates",
            "deduplication",
            "permission boundaries",
            "rollback",
            "exception queue"
        ],
        "economics_inputs": [
            "records_per_month",
            "admin_hours",
            "error_rate",
            "tool_cost",
            "implementation_hours",
            "exception_hours"
        ],
        "retention_upsell": [
            "managed data quality",
            "forecast reporting",
            "new-system connectors",
            "workflow optimization"
        ],
        "reusable_ip_target": "CRM mapping library, reconciliation checks, and sales-ops workflow pack.",
        "maturity": "learned"
    },
    "support_resolution_routing": {
        "icp": "Support teams with repeatable ticket categories, measurable resolution economics, and a defined human escalation path.",
        "qualification": [
            "ticket_volume_measured",
            "taxonomy_defined",
            "knowledge_sources_authorized",
            "escalation_sla_defined"
        ],
        "measurable_value": "Reduced time to resolution and handling cost without degrading quality or escalation safety.",
        "decision_rule": {
            "deterministic_default": "Apply routing, entitlement, priority, and escalation policy.",
            "ai_when": "Intent classification, retrieval, or draft resolution needs language reasoning."
        },
        "delivery_playbook": [
            "baseline categories and resolution",
            "connect approved knowledge",
            "implement routing and drafts",
            "add confidence gates and escalation",
            "evaluate quality and cost"
        ],
        "qa_checklist": [
            "routing precision",
            "grounded answers",
            "permission checks",
            "confidence threshold",
            "escalation SLA",
            "resolution audit"
        ],
        "economics_inputs": [
            "ticket_volume",
            "handling_minutes",
            "resolution_rate",
            "model_cost",
            "review_hours",
            "reopen_rate"
        ],
        "retention_upsell": [
            "managed knowledge refresh",
            "quality monitoring",
            "additional channels",
            "resolution automation"
        ],
        "reusable_ip_target": "Support taxonomy, grounded-response evals, and escalation router.",
        "maturity": "learned"
    },
    "back_office_document_data_workflows": {
        "icp": "Operations teams processing recurring documents or records with explicit schemas, review rules, and measurable manual effort.",
        "qualification": [
            "document_volume_measured",
            "target_schema_defined",
            "source_authority_verified",
            "review_threshold_defined"
        ],
        "measurable_value": "Reduced processing time and error/rework cost for accepted records.",
        "decision_rule": {
            "deterministic_default": "Validate formats, transform fields, reconcile totals, and route exceptions.",
            "ai_when": "Documents require extraction or classification beyond deterministic parsing."
        },
        "delivery_playbook": [
            "sample authorized documents",
            "define schema and acceptance set",
            "build extraction and validation",
            "add review thresholds",
            "reconcile outputs"
        ],
        "qa_checklist": [
            "field accuracy",
            "schema conformance",
            "total reconciliation",
            "PII handling",
            "exception routing",
            "audit retention"
        ],
        "economics_inputs": [
            "documents_per_month",
            "minutes_per_document",
            "error_cost",
            "model_cost",
            "review_rate",
            "implementation_hours"
        ],
        "retention_upsell": [
            "managed exception handling",
            "new document types",
            "system posting",
            "compliance reporting"
        ],
        "reusable_ip_target": "Document schemas, extraction evals, validators, and posting connectors.",
        "maturity": "learned"
    },
    "multi_system_operational_integration": {
        "icp": "Organizations with a high-value workflow crossing multiple APIs where failures, rekeying, or inconsistent state create measurable cost.",
        "qualification": [
            "systems_and_owners_identified",
            "api_access_authorized",
            "source_of_truth_defined",
            "rollback_owner_named"
        ],
        "measurable_value": "Reduced rekeying, cycle time, and reconciliation failures across the integrated workflow.",
        "decision_rule": {
            "deterministic_default": "Orchestrate APIs, map schemas, enforce idempotency, retry, and reconcile.",
            "ai_when": "Unstructured inputs or exception triage need bounded reasoning."
        },
        "delivery_playbook": [
            "map systems and authority",
            "define source of truth",
            "implement idempotent orchestration",
            "add observability and rollback",
            "run failure-mode QA"
        ],
        "qa_checklist": [
            "idempotency",
            "retry safety",
            "schema drift",
            "partial failure recovery",
            "least privilege",
            "end-to-end reconciliation"
        ],
        "economics_inputs": [
            "transactions_per_month",
            "rekey_hours",
            "failure_cost",
            "integration_cost",
            "monitoring_cost",
            "exception_hours"
        ],
        "retention_upsell": [
            "managed monitoring",
            "additional systems",
            "SLA reporting",
            "workflow optimization"
        ],
        "reusable_ip_target": "Connector adapters, orchestration primitives, and reconciliation harness.",
        "maturity": "learned"
    }
}
REUSABLE_IP_TYPES = {
    "workflow", "connector", "eval", "playbook", "prompt",
    "code_component", "dataset",
}
REUSABLE_IP_MATURITY = {
    "learned": 0,
    "paid_validated": 1,
    "repeatable_positive_margin": 2,
    "scale_candidate": 3,
    "productize_candidate": 4,
}
BUYER_EVENT_STATES = {
    "response_received",  # Legacy compatibility; new evidence should be explicit.
    "buyer_reply", "interview", "offer",
}
PIPELINE_TRANSITIONS = {
    "payment_rail_blocked": {"qualified", "unqualified", "expired"},
    "qualified": {"proposal_ready", "unqualified", "expired"},
    "proposal_ready": {"submitted", "unqualified", "expired"},
    "submitted": BUYER_EVENT_STATES | {"unqualified", "expired"},
    "response_received": {"buyer_reply", "interview", "offer", "contracted", "unqualified"},
    "buyer_reply": {"interview", "offer", "unqualified"},
    "interview": {"offer", "unqualified"},
    "offer": {"contracted", "unqualified"},
    "contracted": {"executing"},
    "executing": {"qa_passed"},
    "qa_passed": {"delivered"},
    "delivered": {"invoiced"},
    "invoiced": {"collected"},
    "collected": {"withdrawable"},
    "withdrawable": {"received"},
}
TERMINAL_SCREEN_REASONS = {
    "opportunity_expired", "listing_closed", "listing_filled",
    "preferred_qualifications_unmet", "marketplace_application_unavailable",
    "location_ineligible", "non_positive_projected_margin",
    "execution_capabilities_unmet", "personal_data_authority_unverified",
    "credential_access_unsafe", "offer_family_qualification_failed",
    "prohibited_category", "scam_signals_present",
    "deception_required", "unsolicited_contact_disallowed",
    "suppressed_or_opted_out", "execution_confidence_too_low",
}
PIPELINE_EVIDENCE_PREFIXES = {
    "qualified": ("payment_rail:",),
    "proposal_ready": ("proposal:",),
    "submitted": ("submission:",),
    "response_received": ("reply:",),
    "buyer_reply": ("reply:",),
    "interview": ("interview:",),
    "offer": ("offer:",),
    "contracted": ("contract:",),
    "executing": ("contract:",),
    "qa_passed": ("qa:",),
    "delivered": ("delivery:",),
    "invoiced": ("invoice:",),
    "collected": ("verified_payment:",),
    "withdrawable": ("withdrawable_balance:",),
    "received": ("bank_receipt:",),
    "unqualified": ("screen:",),
    "expired": ("expiry:",),
}


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


def finite_number(payload, field, *, minimum=0, maximum=None, required=True):
    value = payload.get(field)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field}_invalid")
    value = float(value)
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{field}_invalid")
    return value


def boolean_flag(payload, field, *, default=False):
    """Accept only explicit JSON booleans for policy-sensitive evidence."""
    value = payload.get(field, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field}_invalid")
    return value


def optional_boolean_flag(payload, field):
    """Preserve missing provider flags instead of guessing a boolean value."""
    if field not in payload or payload[field] is None:
        return None
    return boolean_flag(payload, field)


def capability_set(payload, field):
    """Normalize explicit execution capabilities without guessing from free text."""
    values = payload.get(field, [])
    if not isinstance(values, list):
        raise ValueError(f"{field}_invalid")
    normalized = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field}_invalid")
        capability = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", capability):
            raise ValueError(f"{field}_invalid")
        normalized.add(capability)
    return sorted(normalized)


def enum_list(payload, field, allowed):
    """Normalize a unique ordered list of supported doctrine values."""
    values = payload.get(field, [])
    if not isinstance(values, list):
        raise ValueError(f"{field}_invalid")
    normalized = []
    for value in values:
        item = str(value or "").strip().lower()
        if not item or item not in allowed:
            raise ValueError(f"{field}_invalid")
        if item not in normalized:
            normalized.append(item)
    return normalized


def evidence_refs(values, field):
    """Normalize auditable evidence references without accepting free-form claims."""
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 50:
        raise ValueError(f"{field}_invalid")
    normalized = []
    allowed_prefixes = (
        "https://", "artifact:", "github:", "verified_payment:",
        "verified_margin:", "retention:", "expansion:", "delivery:", "qa:",
    )
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field}_invalid")
        reference = value.strip()
        if not reference or len(reference) > 1000 or not reference.startswith(allowed_prefixes):
            raise ValueError(f"{field}_invalid")
        if reference not in normalized:
            normalized.append(reference)
    return normalized


def offer_evidence_map(payload, offer_phases):
    value = payload.get("offer_evidence", {})
    if not isinstance(value, dict):
        raise ValueError("offer_evidence_invalid")
    normalized = {}
    for phase, refs in value.items():
        normalized_phase = str(phase or "").strip().lower()
        if normalized_phase not in OFFER_PHASES:
            raise ValueError("offer_evidence_phase_invalid")
        if normalized_phase not in offer_phases:
            raise ValueError("offer_evidence_phase_not_declared")
        normalized[normalized_phase] = evidence_refs(
            refs, f"offer_evidence_{normalized_phase}")
    return normalized


def offer_family_selection(payload):
    """Validate an issue #164 offer-family fit without claiming earned mastery."""
    family_id = str(payload.get("offer_family") or "").strip().lower()
    if not family_id:
        if any(field in payload for field in (
                "offer_family_fit_score", "offer_family_qualification",
                "offer_family_evidence")):
            raise ValueError("offer_family_required")
        return {
            "id": None, "catalog_version": OFFER_FAMILY_CATALOG_VERSION,
            "asset_hash": None, "fit_score": 0.0, "qualified": False,
            "qualification": {}, "evidence": [], "maturity": None,
        }
    asset = OFFER_FAMILY_CATALOG.get(family_id)
    if asset is None:
        raise ValueError("offer_family_invalid")
    fit_score = finite_number(
        payload, "offer_family_fit_score", maximum=1, required=False)
    if fit_score is None:
        raise ValueError("offer_family_fit_score_required")
    qualification = payload.get("offer_family_qualification")
    if not isinstance(qualification, dict):
        raise ValueError("offer_family_qualification_invalid")
    required = asset["qualification"]
    if set(qualification) != set(required):
        raise ValueError("offer_family_qualification_keys_invalid")
    normalized_qualification = {}
    for key in required:
        value = qualification[key]
        if not isinstance(value, bool):
            raise ValueError("offer_family_qualification_value_invalid")
        normalized_qualification[key] = value
    evidence = evidence_refs(
        payload.get("offer_family_evidence"), "offer_family_evidence")
    if not evidence:
        raise ValueError("offer_family_evidence_required")
    return {
        "id": family_id,
        "catalog_version": OFFER_FAMILY_CATALOG_VERSION,
        "asset_hash": payload_hash(asset),
        "fit_score": fit_score,
        "qualified": all(normalized_qualification.values()),
        "qualification": normalized_qualification,
        "evidence": evidence,
        "maturity": asset["maturity"],
    }


def reusable_ip_assets(payload):
    values = payload.get("reusable_ip_assets", [])
    if not isinstance(values, list) or len(values) > 50:
        raise ValueError("reusable_ip_assets_invalid")
    normalized = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("reusable_ip_asset_invalid")
        name = str(value.get("name") or "").strip()
        asset_type = str(value.get("type") or "").strip().lower()
        maturity = str(value.get("maturity") or "learned").strip().lower()
        if not name or len(name) > 160:
            raise ValueError("reusable_ip_asset_name_invalid")
        if asset_type not in REUSABLE_IP_TYPES:
            raise ValueError("reusable_ip_asset_type_invalid")
        if maturity not in REUSABLE_IP_MATURITY:
            raise ValueError("reusable_ip_asset_maturity_invalid")
        refs = evidence_refs(value.get("evidence", []), "reusable_ip_asset_evidence")
        if REUSABLE_IP_MATURITY[maturity] >= REUSABLE_IP_MATURITY["paid_validated"]:
            if not any(ref.startswith("verified_payment:") for ref in refs):
                raise ValueError("reusable_ip_paid_validation_evidence_required")
        if REUSABLE_IP_MATURITY[maturity] >= REUSABLE_IP_MATURITY["repeatable_positive_margin"]:
            if not any(ref.startswith("verified_margin:") for ref in refs):
                raise ValueError("reusable_ip_margin_evidence_required")
        if REUSABLE_IP_MATURITY[maturity] >= REUSABLE_IP_MATURITY["scale_candidate"]:
            if not any(ref.startswith("retention:") for ref in refs):
                raise ValueError("reusable_ip_retention_evidence_required")
        if REUSABLE_IP_MATURITY[maturity] >= REUSABLE_IP_MATURITY["productize_candidate"]:
            if not any(ref.startswith("expansion:") for ref in refs):
                raise ValueError("reusable_ip_expansion_evidence_required")
        normalized.append({
            "name": name,
            "type": asset_type,
            "maturity": maturity,
            "evidence": refs,
        })
    return normalized


def derive_offer_architecture(opportunity, proposal_price_cents, milestones):
    """Build a family-specific, evidence-labeled issue #164 offer ladder."""
    selection = opportunity.get("offer_family_selection") or {}
    family_id = selection.get("id")
    if not family_id:
        return None
    asset = OFFER_FAMILY_CATALOG.get(family_id)
    if asset is None or selection.get("asset_hash") != payload_hash(asset):
        raise ValueError("offer_family_asset_mismatch")
    if selection.get("maturity") != "learned":
        raise ValueError("offer_family_maturity_requires_ledger")

    declared = set(opportunity.get("offer_phases") or [])
    qa = asset["qa_checklist"]
    delivery = asset["delivery_playbook"]
    outcome_terms = None
    if opportunity.get("outcome_pricing"):
        outcome_terms = {
            "opportunity_id": opportunity["id"],
            "success_definition": opportunity["outcome_success_definition"],
            "attribution_method": opportunity["outcome_attribution_method"],
            "exclusions": opportunity["outcome_exclusions"],
            "fee_cap_cents": opportunity["outcome_fee_cap_cents"],
            "unit_fee_cents": opportunity["outcome_unit_fee_cents"],
            "human_escalation_rule": opportunity["human_escalation_rule"],
        }
        outcome_terms["terms_hash"] = payload_hash(outcome_terms)

    stages = [
        {
            "id": "diagnostic_pilot",
            "status": ("included" if declared.intersection(
                {"diagnostic", "pilot"}) else "recommended_not_included"),
            "commercial_model": "fixed_bounded",
            "scope_basis": delivery[:2],
            "acceptance_tests": qa[:2],
        },
        {
            "id": "implementation",
            "status": ("included" if "implementation" in declared
                       else "recommended_not_included"),
            "commercial_model": "fixed_bounded",
            "scope_basis": delivery[1:4],
            "acceptance_tests": qa[:4],
        },
        {
            "id": "managed_recurring",
            "status": ("included" if "managed_recurring" in declared
                       else "recommended_not_included"),
            "commercial_model": "recurring_base_platform_fee",
            "scope_basis": asset["retention_upsell"],
            "acceptance_tests": qa[-2:],
        },
        {
            "id": "outcome_component",
            "status": ("included" if outcome_terms else "not_configured"),
            "commercial_model": "auditable_usage_or_outcome_capped",
            "scope_basis": ([asset["measurable_value"]]
                            if outcome_terms else []),
            "acceptance_tests": (
                [qa[-1], "accepted terms hash and cap resolve before accrual"]
                if outcome_terms else []),
            "terms": outcome_terms,
        },
    ]
    economics = dict(opportunity["unit_economics"])
    economics.update({
        "proposal_price_cents": int(proposal_price_cents),
        "milestone_total_cents": sum(
            milestone["amount_cents"] for milestone in milestones),
        "required_input_keys": asset["economics_inputs"],
        "evidence_status": "projected_not_collected",
    })
    architecture = {
        "family_id": family_id,
        "catalog_version": selection["catalog_version"],
        "family_asset_hash": selection["asset_hash"],
        "maturity": "learned",
        "stages": stages,
        "economics": economics,
        "reusable_ip_target": asset["reusable_ip_target"],
        "evidence_status": "prepared_not_contracted_not_revenue",
    }
    architecture["architecture_hash"] = payload_hash(architecture)
    return architecture


def normalize_recurring_terms(proposal, recurring_base_fee_cents):
    """Normalize managed-service terms without accepting or billing them."""
    value = proposal.get("recurring_terms")
    if recurring_base_fee_cents <= 0:
        if value is not None:
            raise ValueError("recurring_terms_fee_required")
        return None
    if not isinstance(value, dict):
        raise ValueError("recurring_terms_required")
    cadence = str(value.get("billing_cadence") or "").strip().lower()
    if cadence not in {"weekly", "monthly", "quarterly", "annual"}:
        raise ValueError("recurring_billing_cadence_invalid")
    raw_services = value.get("included_services")
    if not isinstance(raw_services, list) or not 1 <= len(raw_services) <= 20:
        raise ValueError("recurring_included_services_invalid")
    services = []
    for service in raw_services:
        service = _proposal_text(service, "recurring_included_service", 500)
        if service not in services:
            services.append(service)
    terms = {
        "base_fee_cents": int(recurring_base_fee_cents),
        "billing_cadence": cadence,
        "included_services": services,
        "included_usage_definition": _proposal_text(
            value.get("included_usage_definition"),
            "recurring_included_usage_definition", 1000),
        "support_boundaries": _proposal_text(
            value.get("support_boundaries"), "recurring_support_boundaries", 1000),
        "exception_boundaries": _proposal_text(
            value.get("exception_boundaries"),
            "recurring_exception_boundaries", 1000),
        "renewal_terms": _proposal_text(
            value.get("renewal_terms"), "recurring_renewal_terms", 1000),
        "termination_terms": _proposal_text(
            value.get("termination_terms"), "recurring_termination_terms", 1000),
        "evidence_status": "proposed_not_accepted_not_revenue",
    }
    terms["terms_hash"] = payload_hash(terms)
    return terms


def validate_offer_pricing(architecture, milestones, fixed_price_cents,
                           recurring_base_fee_cents, recurring_terms):
    """Bind fixed, recurring, and outcome pricing without conflating them."""
    bound = any(
        milestone.get("stage_id") or milestone.get("acceptance_criteria")
        for milestone in milestones)
    if architecture is None:
        if bound or recurring_base_fee_cents:
            raise ValueError("offer_pricing_architecture_required")
        return None

    stages = {stage["id"]: stage for stage in architecture["stages"]}
    included_fixed = {
        stage_id for stage_id in ("diagnostic_pilot", "implementation")
        if stages[stage_id]["status"] == "included"
    }
    if not included_fixed:
        raise ValueError("offer_fixed_stage_required")
    stage_totals = {stage_id: 0 for stage_id in included_fixed}
    for milestone in milestones:
        stage_id = milestone.get("stage_id")
        if stage_id not in included_fixed:
            raise ValueError("milestone_offer_stage_invalid")
        criteria = milestone.get("acceptance_criteria") or []
        if not criteria:
            raise ValueError("milestone_acceptance_criteria_required")
        allowed = set(stages[stage_id]["acceptance_tests"])
        if any(criterion not in allowed for criterion in criteria):
            raise ValueError("milestone_acceptance_criteria_unbound")
        stage_totals[stage_id] += milestone["amount_cents"]
    if any(not stage_totals[stage_id] for stage_id in included_fixed):
        raise ValueError("included_fixed_stage_milestone_required")

    recurring_included = stages["managed_recurring"]["status"] == "included"
    if recurring_included and recurring_base_fee_cents <= 0:
        raise ValueError("recurring_base_fee_required")
    if not recurring_included and recurring_base_fee_cents:
        raise ValueError("recurring_base_fee_stage_not_included")

    outcome_stage = stages["outcome_component"]
    outcome_cap = None
    if outcome_stage["status"] == "included":
        outcome_cap = outcome_stage["terms"]["fee_cap_cents"]
        if not isinstance(outcome_cap, int) or outcome_cap <= 0:
            raise ValueError("outcome_fee_cap_invalid")

    composition = {
        "fixed_one_time_total_cents": int(fixed_price_cents),
        "fixed_stage_totals_cents": {
            key: stage_totals[key] for key in sorted(stage_totals)},
        "recurring_base_fee_cents": int(recurring_base_fee_cents),
        "recurring_terms_hash": (
            recurring_terms["terms_hash"] if recurring_terms else None),
        "outcome_fee_cap_cents": outcome_cap,
        "outcome_fee_in_fixed_total_cents": 0,
        "currency_timing": {
            "fixed": "one_time_milestones",
            "recurring": ("separate_recurring_period"
                          if recurring_included else "not_included"),
            "outcome": ("separate_verified_events_capped"
                        if outcome_cap is not None else "not_configured"),
        },
        "evidence_status": "proposed_not_contracted_not_collected",
    }
    composition["composition_hash"] = payload_hash(composition)
    return composition


def projected_unit_economics(opportunity):
    """Return explicit projected economics; these are not collected revenue."""
    contract_value = opportunity["contract_value_cents"]
    total_cost = (
        opportunity["delivery_cost_cents"]
        + opportunity["inference_cost_cents"]
        + opportunity["cac_cents"]
    )
    contribution = contract_value - total_cost
    margin = contribution / contract_value if contract_value else 0
    return {
        "contract_value_cents": contract_value,
        "delivery_cost_cents": opportunity["delivery_cost_cents"],
        "inference_cost_cents": opportunity["inference_cost_cents"],
        "cac_cents": opportunity["cac_cents"],
        "cost_estimates_complete": opportunity["cost_estimates_complete"],
        "cost_evidence_status": (
            "complete_projected_inputs"
            if opportunity["cost_estimates_complete"]
            else "incomplete_projected_inputs"
        ),
        "projected_contribution_cents": contribution,
        "projected_contribution_margin": round(margin, 6),
        "human_operating_hours": opportunity["human_operating_hours"],
        "projected_revenue_per_human_hour": round(
            contract_value / 100 / opportunity["human_operating_hours"], 2
        ),
        "projected_contribution_per_human_hour": round(
            contribution / 100 / opportunity["human_operating_hours"], 2
        ),
        "evidence_status": "projected_not_collected",
    }


def canonical_url(value):
    if not value:
        return ""
    try:
        parsed = urlsplit(str(value).strip())
    except ValueError as exc:
        raise ValueError("url_invalid") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url_invalid")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url_credentials_forbidden")
    sensitive_query_keys = {
        "access_token", "api_key", "apikey", "auth", "authorization",
        "client_secret", "code", "credential", "credentials", "id_token",
        "key", "password", "private_key", "refresh_token", "session_id",
        "session_token", "signature", "signed", "secret", "token",
        "webhook_secret", "x_api_key",
    }
    if any(
        re.sub(r"[-.\s]+", "_", key.strip().lower())
        in sensitive_query_keys
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise ValueError("url_sensitive_query_forbidden")
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host + port, path, parsed.query, ""))


def stable_id(source, external_id, url):
    # A provider's immutable external ID wins over a mutable/listing URL.
    identity = f"{source.lower()}|{external_id.lower() or url.lower()}"
    return "opp_" + hashlib.sha256(identity.encode()).hexdigest()[:20]


def payload_hash(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        encoded = repr(value)
    return hashlib.sha256(encoded.encode()).hexdigest()


def normalize(payload, *, now=None, max_age_days=DEFAULT_MAX_AGE_DAYS):
    if not isinstance(payload, dict):
        raise ValueError("opportunity_object_required")
    now = now or utc_now()
    title = str(payload.get("title") or "").strip()
    source = str(payload.get("source") or "").strip()
    external_id = str(payload.get("external_id") or "").strip()
    url = canonical_url(payload.get("url"))
    if urlsplit(url).scheme != "https":
        raise ValueError("opportunity_url_https_required")
    if not title:
        raise ValueError("title_required")
    if not source:
        raise ValueError("source_required")
    if not external_id and not url:
        raise ValueError("external_id_or_url_required")
    opportunity_id = stable_id(source, external_id, url)

    observed = parse_time(payload.get("observed_at"), "observed_at")
    if observed > now + MAX_FUTURE_SKEW:
        raise ValueError("observed_at_future")
    if observed < now - timedelta(days=max_age_days):
        raise ValueError("opportunity_stale")
    published = None
    listing_age_days = None
    if payload.get("published_at") is not None:
        published = parse_time(payload.get("published_at"), "published_at")
        if published > now + MAX_FUTURE_SKEW:
            raise ValueError("published_at_future")
        if published > observed + MAX_FUTURE_SKEW:
            raise ValueError("published_at_after_observation")
        listing_age_days = max(
            0, (now - published).total_seconds() / 86400)
    expires = None
    if payload.get("expires_at") is not None:
        expires = parse_time(payload.get("expires_at"), "expires_at")

    payout_cents = finite_number(payload, "payout_cents", minimum=1)
    if not payout_cents.is_integer():
        raise ValueError("payout_cents_invalid")
    effort_hours = finite_number(payload, "effort_hours", minimum=0.25, maximum=10000)
    time_to_cash_days = finite_number(payload, "time_to_cash_days", minimum=0, maximum=3650)
    contract_value_cents = finite_number(
        payload, "contract_value_cents", minimum=1, required=False)
    economic_value_cents = finite_number(
        payload, "economic_value_cents", minimum=0, required=False)
    delivery_cost_cents = finite_number(
        payload, "delivery_cost_cents", minimum=0, required=False)
    inference_cost_cents = finite_number(
        payload, "inference_cost_cents", minimum=0, required=False)
    cac_cents = finite_number(payload, "cac_cents", minimum=0, required=False)
    cost_estimates_complete = all(
        value is not None
        for value in (delivery_cost_cents, inference_cost_cents, cac_cents)
    )
    human_operating_hours = finite_number(
        payload, "human_operating_hours", minimum=0.01, maximum=10000,
        required=False)
    for field, value in (
        ("contract_value_cents", contract_value_cents),
        ("economic_value_cents", economic_value_cents),
        ("delivery_cost_cents", delivery_cost_cents),
        ("inference_cost_cents", inference_cost_cents),
        ("cac_cents", cac_cents),
    ):
        if value is not None and not value.is_integer():
            raise ValueError(f"{field}_invalid")
    family_selection = offer_family_selection(payload)
    buyer_stage = str(payload.get("buyer_stage") or "prospect").strip().lower()
    if buyer_stage not in BUYER_STAGE_SCORES:
        raise ValueError("buyer_stage_invalid")
    raw_buyer_stage_evidence_url = str(
        payload.get("buyer_stage_evidence_url") or "").strip()
    parsed_buyer_stage_evidence_url = urlsplit(raw_buyer_stage_evidence_url)
    if (parsed_buyer_stage_evidence_url.username is not None
            or parsed_buyer_stage_evidence_url.password is not None):
        raise ValueError("buyer_stage_evidence_url_credentials_forbidden")
    buyer_stage_evidence_url = canonical_url(raw_buyer_stage_evidence_url)
    buyer_stage_evidence_at = None
    if buyer_stage != "prospect":
        if not buyer_stage_evidence_url:
            raise ValueError("buyer_stage_evidence_url_required")
        if urlsplit(buyer_stage_evidence_url).scheme != "https":
            raise ValueError("buyer_stage_evidence_url_https_required")
        buyer_stage_evidence_at = parse_time(
            payload.get("buyer_stage_evidence_at"),
            "buyer_stage_evidence_at")
        if buyer_stage_evidence_at > now + MAX_FUTURE_SKEW:
            raise ValueError("buyer_stage_evidence_at_future")
        if buyer_stage_evidence_at < now - timedelta(days=max_age_days):
            raise ValueError("buyer_stage_evidence_stale")
    offer_phases = enum_list(payload, "offer_phases", OFFER_PHASES)
    offer_evidence = offer_evidence_map(payload, offer_phases)
    ip_assets = reusable_ip_assets(payload)
    outcome_pricing = boolean_flag(payload, "outcome_pricing")
    outcome_success_definition = str(
        payload.get("outcome_success_definition") or "").strip()
    outcome_attribution_method = str(
        payload.get("outcome_attribution_method") or "").strip()
    outcome_fee_cap_cents = finite_number(
        payload, "outcome_fee_cap_cents", minimum=1, required=False)
    outcome_unit_fee_cents = finite_number(
        payload, "outcome_unit_fee_cents", minimum=1, required=False)
    human_escalation_defined = boolean_flag(
        payload, "human_escalation_defined")
    human_escalation_rule = str(
        payload.get("human_escalation_rule") or "").strip()
    raw_exclusions = payload.get("outcome_exclusions", [])
    if not isinstance(raw_exclusions, list) or len(raw_exclusions) > 20:
        raise ValueError("outcome_exclusions_invalid")
    outcome_exclusions = []
    for exclusion in raw_exclusions:
        if not isinstance(exclusion, str) or not exclusion.strip():
            raise ValueError("outcome_exclusion_invalid")
        exclusion = exclusion.strip()
        if len(exclusion) > 500:
            raise ValueError("outcome_exclusion_too_long")
        if exclusion not in outcome_exclusions:
            outcome_exclusions.append(exclusion)
    if outcome_fee_cap_cents is not None and not outcome_fee_cap_cents.is_integer():
        raise ValueError("outcome_fee_cap_cents_invalid")
    if (outcome_unit_fee_cents is not None
            and not outcome_unit_fee_cents.is_integer()):
        raise ValueError("outcome_unit_fee_cents_invalid")
    if outcome_pricing:
        if "outcome_pricing" not in offer_phases:
            raise ValueError("outcome_pricing_phase_required")
        if not outcome_success_definition:
            raise ValueError("outcome_success_definition_required")
        if not outcome_attribution_method:
            raise ValueError("outcome_attribution_method_required")
        if not outcome_exclusions:
            raise ValueError("outcome_exclusions_required")
        if outcome_fee_cap_cents is None:
            raise ValueError("outcome_fee_cap_cents_required")
        if not human_escalation_defined or not human_escalation_rule:
            raise ValueError("outcome_human_escalation_required")
        if outcome_unit_fee_cents is None:
            raise ValueError("outcome_unit_fee_cents_required")
        if outcome_unit_fee_cents > outcome_fee_cap_cents:
            raise ValueError("outcome_unit_fee_exceeds_cap")
    required_capabilities = capability_set(payload, "required_execution_capabilities")
    available_capabilities = capability_set(payload, "available_execution_capabilities")
    application_cost_units = finite_number(
        payload, "application_cost_units", minimum=0, maximum=10000, required=False)
    application_units_balance = finite_number(
        payload, "application_units_balance", minimum=0, maximum=1000000, required=False)
    positions_to_hire = finite_number(
        payload, "positions_to_hire", minimum=1, maximum=10000, required=False)
    hires_for_listing = finite_number(
        payload, "hires_for_listing", minimum=0, maximum=10000, required=False)
    proposal_count_min = finite_number(
        payload, "proposal_count_min", minimum=0, maximum=1000000, required=False)
    proposal_count_max = finite_number(
        payload, "proposal_count_max", minimum=0, maximum=1000000, required=False)
    if application_cost_units is not None and not application_cost_units.is_integer():
        raise ValueError("application_cost_units_invalid")
    if application_units_balance is not None and not application_units_balance.is_integer():
        raise ValueError("application_units_balance_invalid")
    if positions_to_hire is not None and not positions_to_hire.is_integer():
        raise ValueError("positions_to_hire_invalid")
    if hires_for_listing is not None and not hires_for_listing.is_integer():
        raise ValueError("hires_for_listing_invalid")
    if ((proposal_count_min is None) != (proposal_count_max is None)
            or (proposal_count_min is not None
                and (not proposal_count_min.is_integer()
                     or not proposal_count_max.is_integer()
                     or proposal_count_min > proposal_count_max))):
        raise ValueError("proposal_count_range_invalid")
    application_balance_observed = None
    if payload.get("application_balance_observed_at") is not None:
        application_balance_observed = parse_time(
            payload.get("application_balance_observed_at"),
            "application_balance_observed_at")
        if application_balance_observed > now + MAX_FUTURE_SKEW:
            raise ValueError("application_balance_observed_at_future")
    if application_cost_units and application_units_balance is not None:
        if application_balance_observed is None:
            raise ValueError("application_balance_observed_at_required")
        if application_balance_observed < now - MAX_APPLICATION_BALANCE_AGE:
            raise ValueError("application_balance_stale")
    payment_rail_clear = boolean_flag(payload, "payment_rail_clear")
    payment_rail_status = str(
        payload.get("payment_rail_status") or
        ("clear" if payment_rail_clear else "unclear")
    ).strip().lower()
    if payment_rail_status not in {"clear", "temporarily_unavailable", "unclear"}:
        raise ValueError("payment_rail_status_invalid")
    if payment_rail_clear != (payment_rail_status == "clear"):
        raise ValueError("payment_rail_evidence_conflict")
    platform_allows_automation = boolean_flag(payload, "platform_allows_automation")
    authenticated_channel = boolean_flag(payload, "authenticated_channel")
    submission_authorized = boolean_flag(payload, "submission_authorized")
    submission_authorization_id = payload.get(
        "submission_authorization_opportunity_id")
    submission_authorized_at = None
    if submission_authorized:
        if (not isinstance(submission_authorization_id, str)
                or not submission_authorization_id.strip()):
            raise ValueError("submission_authorization_opportunity_id_required")
        submission_authorization_id = submission_authorization_id.strip()
        if submission_authorization_id != opportunity_id:
            raise ValueError("submission_authorization_opportunity_mismatch")
        submission_authorized_at = parse_time(
            payload.get("submission_authorized_at"), "submission_authorized_at")
        if submission_authorized_at > now + MAX_FUTURE_SKEW:
            raise ValueError("submission_authorized_at_future")
        if submission_authorized_at < now - MAX_SUBMISSION_AUTHORIZATION_AGE:
            raise ValueError("submission_authorization_stale")
    application_spend_authorized = boolean_flag(
        payload, "application_spend_authorized")
    application_spend_authorization_id = payload.get(
        "application_spend_authorization_opportunity_id")
    application_spend_authorized_units = None
    application_spend_authorized_at = None
    if application_spend_authorized:
        if not application_cost_units:
            raise ValueError("application_spend_authorization_unnecessary")
        if (not isinstance(application_spend_authorization_id, str)
                or not application_spend_authorization_id.strip()):
            raise ValueError(
                "application_spend_authorization_opportunity_id_required")
        application_spend_authorization_id = (
            application_spend_authorization_id.strip())
        if application_spend_authorization_id != opportunity_id:
            raise ValueError("application_spend_authorization_opportunity_mismatch")
        application_spend_authorized_units = finite_number(
            payload, "application_spend_authorized_units", minimum=0,
            maximum=10000)
        if (not application_spend_authorized_units.is_integer()
                or application_spend_authorized_units != application_cost_units):
            raise ValueError("application_spend_authorized_units_mismatch")
        application_spend_authorized_at = parse_time(
            payload.get("application_spend_authorized_at"),
            "application_spend_authorized_at")
        if application_spend_authorized_at > now + MAX_FUTURE_SKEW:
            raise ValueError("application_spend_authorized_at_future")
        if (application_spend_authorized_at
                < now - MAX_APPLICATION_SPEND_AUTHORIZATION_AGE):
            raise ValueError("application_spend_authorization_stale")
    requires_credential_access = boolean_flag(payload, "requires_credential_access")
    credential_access_method = str(
        payload.get("credential_access_method") or
        ("unclear" if requires_credential_access else "none")
    ).strip().lower()
    normalized = {
        "id": opportunity_id,
        "source": source,
        "external_id": external_id,
        "url": url,
        "title": title,
        "description": str(payload.get("description") or "").strip(),
        "observed_at": observed.isoformat(),
        "published_at": published.isoformat() if published else None,
        "listing_age_days": listing_age_days,
        "expires_at": expires.isoformat() if expires else None,
        "expired": expires is not None and expires <= now,
        "payout_cents": int(payout_cents),
        "currency": str(payload.get("currency") or "USD").strip().upper(),
        "effort_hours": effort_hours,
        "time_to_cash_days": time_to_cash_days,
        "buyer_stage": buyer_stage,
        "buyer_stage_score": BUYER_STAGE_SCORES[buyer_stage],
        "buyer_stage_evidence_url": (
            buyer_stage_evidence_url if buyer_stage != "prospect" else None),
        "buyer_stage_evidence_at": (
            buyer_stage_evidence_at.isoformat()
            if buyer_stage_evidence_at is not None else None),
        "offer_family": family_selection["id"],
        "offer_family_selection": family_selection,
        "payment_history_score": finite_number(
            payload, "payment_history_score", maximum=1, required=False),
        "contract_value_cents": int(contract_value_cents or payout_cents),
        "economic_value_cents": int(economic_value_cents or payout_cents),
        "delivery_cost_cents": int(delivery_cost_cents or 0),
        "inference_cost_cents": int(inference_cost_cents or 0),
        "cac_cents": int(cac_cents or 0),
        "cost_estimates_complete": cost_estimates_complete,
        "human_operating_hours": human_operating_hours or effort_hours,
        "measurable_outcome": boolean_flag(payload, "measurable_outcome"),
        "automation_potential": finite_number(
            payload, "automation_potential", maximum=1, required=False),
        "delivery_risk": finite_number(
            payload, "delivery_risk", maximum=1, required=False),
        "compliance_risk": finite_number(
            payload, "compliance_risk", maximum=1, required=False),
        "reusable_ip_potential": finite_number(
            payload, "reusable_ip_potential", maximum=1, required=False),
        "offer_phases": offer_phases,
        "offer_evidence": offer_evidence,
        "reusable_ip_assets": ip_assets,
        "reusable_ip_summary": {
            "asset_count": len(ip_assets),
            "paid_validated_count": sum(
                REUSABLE_IP_MATURITY[asset["maturity"]] >=
                REUSABLE_IP_MATURITY["paid_validated"]
                for asset in ip_assets
            ),
            "evidence_status": "captured_not_revenue",
        },
        "outcome_pricing": outcome_pricing,
        "outcome_success_definition": (
            outcome_success_definition if outcome_pricing else None),
        "outcome_attribution_method": (
            outcome_attribution_method if outcome_pricing else None),
        "outcome_fee_cap_cents": (
            int(outcome_fee_cap_cents) if outcome_fee_cap_cents is not None else None),
        "outcome_unit_fee_cents": (
            int(outcome_unit_fee_cents)
            if outcome_unit_fee_cents is not None else None),
        "outcome_exclusions": outcome_exclusions if outcome_pricing else [],
        "human_escalation_defined": human_escalation_defined,
        "human_escalation_rule": (
            human_escalation_rule if outcome_pricing else None),
        "buyer_intent": finite_number(payload, "buyer_intent", maximum=1),
        "win_probability": finite_number(payload, "win_probability", maximum=1),
        "execution_confidence": finite_number(payload, "execution_confidence", maximum=1),
        "payment_risk": finite_number(payload, "payment_risk", maximum=1),
        "reuse_value": finite_number(payload, "reuse_value", maximum=1),
        "recurring_value": finite_number(payload, "recurring_value", maximum=1),
        "prohibited_category": str(payload.get("prohibited_category") or "").strip().lower(),
        "scam_signals": [str(x).strip() for x in (payload.get("scam_signals") or []) if str(x).strip()],
        "requires_deception": boolean_flag(payload, "requires_deception"),
        "requires_owner_identity": boolean_flag(payload, "requires_owner_identity"),
        "unsolicited_direct_contact": boolean_flag(
            payload, "unsolicited_direct_contact"),
        "suppressed": boolean_flag(payload, "suppressed"),
        "opted_out": boolean_flag(payload, "opted_out"),
        "payment_rail_status": payment_rail_status,
        "platform_allows_automation": platform_allows_automation,
        "authenticated_channel": authenticated_channel,
        "submission_authorized": submission_authorized,
        "submission_authorization_opportunity_id": (
            submission_authorization_id if submission_authorized else None),
        "submission_authorized_at": (
            submission_authorized_at.isoformat()
            if submission_authorized_at else None),
        "submission_channel_status": str(
            payload.get("submission_channel_status") or
            ("available" if authenticated_channel else "unclear")
        ).strip().lower(),
        "listing_open": boolean_flag(payload, "listing_open", default=True),
        "positions_to_hire": (int(positions_to_hire)
                              if positions_to_hire is not None else None),
        "hires_for_listing": (int(hires_for_listing)
                              if hires_for_listing is not None else None),
        "proposal_count_min": (int(proposal_count_min)
                               if proposal_count_min is not None else None),
        "proposal_count_max": (int(proposal_count_max)
                               if proposal_count_max is not None else None),
        "preferred_qualifications_met": boolean_flag(
            payload, "preferred_qualifications_met", default=True),
        "marketplace_application_allowed": optional_boolean_flag(
            payload, "marketplace_application_allowed"),
        "location_eligible": optional_boolean_flag(payload, "location_eligible"),
        "direct_contract_proposal_available": optional_boolean_flag(
            payload, "direct_contract_proposal_available"),
        "application_cost_units": int(application_cost_units or 0),
        "application_units_balance": (int(application_units_balance)
                                      if application_units_balance is not None else None),
        "application_balance_observed_at": (
            application_balance_observed.isoformat()
            if application_balance_observed else None),
        "application_spend_authorized": application_spend_authorized,
        "application_spend_authorization_opportunity_id": (
            application_spend_authorization_id
            if application_spend_authorized else None),
        "application_spend_authorized_units": (
            int(application_spend_authorized_units)
            if application_spend_authorized_units is not None else None),
        "application_spend_authorized_at": (
            application_spend_authorized_at.isoformat()
            if application_spend_authorized_at else None),
        "requires_personal_data_collection": boolean_flag(
            payload, "requires_personal_data_collection"),
        "personal_data_authorized": boolean_flag(payload, "personal_data_authorized"),
        "requires_credential_access": requires_credential_access,
        "credential_access_method": credential_access_method,
        "required_execution_capabilities": required_capabilities,
        "available_execution_capabilities": available_capabilities,
        "missing_execution_capabilities": sorted(
            set(required_capabilities) - set(available_capabilities)),
    }
    if not re.fullmatch(r"[A-Z]{3}", normalized["currency"]):
        raise ValueError("currency_invalid")
    if normalized["submission_channel_status"] not in {
            "available", "temporarily_unavailable", "unclear"}:
        raise ValueError("submission_channel_status_invalid")
    if normalized["credential_access_method"] not in {
            "none", "provider_managed", "tokenized", "raw", "unclear"}:
        raise ValueError("credential_access_method_invalid")
    if normalized["payment_history_score"] is None:
        normalized["payment_history_score"] = 0.5
    if normalized["automation_potential"] is None:
        normalized["automation_potential"] = 0.5
    if normalized["delivery_risk"] is None:
        normalized["delivery_risk"] = 0.5
    if normalized["compliance_risk"] is None:
        normalized["compliance_risk"] = 0.5
    if normalized["reusable_ip_potential"] is None:
        normalized["reusable_ip_potential"] = normalized["reuse_value"]
    normalized["unit_economics"] = projected_unit_economics(normalized)
    return normalized


def screen(opportunity):
    if opportunity["expired"]:
        return False, "opportunity_expired"
    if (opportunity["offer_family"] is not None
            and not opportunity["offer_family_selection"]["qualified"]):
        return False, "offer_family_qualification_failed"
    if opportunity["unit_economics"]["projected_contribution_cents"] <= 0:
        return False, "non_positive_projected_margin"
    if not opportunity["listing_open"]:
        return False, "listing_closed"
    if opportunity["marketplace_application_allowed"] is False:
        return False, "marketplace_application_unavailable"
    if opportunity["location_eligible"] is False:
        return False, "location_ineligible"
    if (opportunity["positions_to_hire"] is not None
            and opportunity["hires_for_listing"] is not None
            and opportunity["hires_for_listing"] >= opportunity["positions_to_hire"]):
        return False, "listing_filled"
    if not opportunity["preferred_qualifications_met"]:
        return False, "preferred_qualifications_unmet"
    if (opportunity["application_cost_units"] > 0
            and opportunity["application_units_balance"] is None):
        return False, "application_balance_unverified"
    if (opportunity["application_units_balance"] is not None
            and opportunity["application_cost_units"]
            > opportunity["application_units_balance"]):
        return False, "insufficient_application_units"
    if opportunity["missing_execution_capabilities"]:
        return False, "execution_capabilities_unmet"
    if (opportunity["requires_personal_data_collection"]
            and not opportunity["personal_data_authorized"]):
        return False, "personal_data_authority_unverified"
    if (opportunity["requires_credential_access"]
            and opportunity["credential_access_method"] not in {
                "provider_managed", "tokenized"}):
        return False, "credential_access_unsafe"
    if opportunity["prohibited_category"] in PROHIBITED_CATEGORIES:
        return False, "prohibited_category"
    if opportunity["scam_signals"]:
        return False, "scam_signals_present"
    if opportunity["requires_deception"]:
        return False, "deception_required"
    if opportunity["unsolicited_direct_contact"]:
        return False, "unsolicited_contact_disallowed"
    if opportunity["suppressed"] or opportunity["opted_out"]:
        return False, "suppressed_or_opted_out"
    if opportunity["payment_rail_status"] == "unclear":
        return False, "payment_rail_unclear"
    if opportunity["execution_confidence"] < 0.6:
        return False, "execution_confidence_too_low"
    return True, "eligible"


def score(opportunity):
    """Return a bounded doctrine-aligned 0-100 score with explicit components."""
    expected_value = opportunity["payout_cents"] * opportunity["win_probability"]
    dollars_per_hour = expected_value / 100 / opportunity["effort_hours"]
    value_score = min(dollars_per_hour / 100, 1)
    speed_score = max(0, 1 - opportunity["time_to_cash_days"] / 60)
    contract_value_score = min(opportunity["contract_value_cents"] / 500000, 1)
    value_to_fee = (
        opportunity["economic_value_cents"]
        / max(opportunity["contract_value_cents"] * 3, 1)
    )
    economic_value_score = min(value_to_fee, 1)
    # Effective leverage must reflect contribution after delivery, API, and
    # acquisition costs; gross revenue per hour can reward loss-making offers.
    cost_estimates_complete = opportunity["cost_estimates_complete"]
    leverage_score = (
        max(0, min(
            opportunity["unit_economics"][
                "projected_contribution_per_human_hour"] / 1000,
            1,
        ))
        if cost_estimates_complete else 0
    )
    margin_score = (
        max(
            0,
            min(
                opportunity["unit_economics"]["projected_contribution_margin"],
                1,
            ),
        )
        if cost_estimates_complete else 0
    )
    remaining_positions = None
    if (opportunity["positions_to_hire"] is not None
            and opportunity["hires_for_listing"] is not None):
        remaining_positions = max(
            opportunity["positions_to_hire"] - opportunity["hires_for_listing"], 1)
    competition_per_opening = (
        (opportunity["proposal_count_max"] or 0) / remaining_positions
        if remaining_positions is not None
        else (opportunity["proposal_count_max"] or 0)
    )
    components = {
        "buyer_intent": 10 * opportunity["buyer_intent"],
        "active_buyer_stage": 10 * opportunity["buyer_stage_score"],
        "offer_family_fit": (
            6 * opportunity["offer_family_selection"]["fit_score"]
            if opportunity["offer_family"] is not None else 0
        ),
        "expected_value": 8 * value_score,
        "contract_value": 7 * contract_value_score,
        "measurable_economic_value": (
            5 * economic_value_score if opportunity["measurable_outcome"] else 0
        ),
        "win_probability": 8 * opportunity["win_probability"],
        "execution_confidence": 10 * opportunity["execution_confidence"],
        "time_to_cash": 8 * speed_score,
        "payment_safety": 6 * (1 - opportunity["payment_risk"]),
        "payment_history": 5 * opportunity["payment_history_score"],
        "reuse_and_recurring": (
            3 * opportunity["reusable_ip_potential"]
            + 3 * opportunity["recurring_value"]
        ),
        "automation_and_margin": (
            5 * opportunity["automation_potential"] + 5 * margin_score
        ),
        "effective_leverage": 7 * leverage_score,
        "delivery_risk": -7.5 * opportunity["delivery_risk"],
        "compliance_risk": -7.5 * opportunity["compliance_risk"],
        "application_cost": -10 * min(
            opportunity["application_cost_units"] /
            max(opportunity["application_units_balance"] or 1, 1), 1),
        "submission_access": {
            "available": 0,
            "unclear": -5,
            "temporarily_unavailable": -25,
        }[opportunity["submission_channel_status"]],
        "competition": -10 * min(competition_per_opening / 50, 1),
        "listing_freshness": -5 * min(
            (opportunity["listing_age_days"] or 0) / 30, 1)
            if opportunity["listing_age_days"] is not None else 0,
    }
    total = max(0, min(sum(components.values()), 100))
    return round(total, 2), {
        key: round(value, 2) for key, value in components.items()
    }

def action_mode(opportunity):
    if (opportunity["platform_allows_automation"] and opportunity["authenticated_channel"]
            and opportunity["submission_authorized"] and not opportunity["requires_owner_identity"]
            and opportunity["cost_estimates_complete"]
            and (opportunity["application_cost_units"] == 0
                 or opportunity["application_spend_authorized"])
            and opportunity["payment_rail_status"] == "clear"
            and opportunity["submission_channel_status"] == "available"):
        return "autonomous_submit"
    return "prepare_only"


def ingest(payloads, *, now=None, max_age_days=DEFAULT_MAX_AGE_DAYS):
    now = now or utc_now()
    accepted, records, by_id = [], [], {}
    rejection_by_index = {}
    for index, payload in enumerate(payloads):
        try:
            item = normalize(payload, now=now, max_age_days=max_age_days)
            record = {"item": item, "index": index,
                      "payload_hash": payload_hash(payload)}
            previous = by_id.get(item["id"])
            if previous:
                previous_observed = previous["item"]["observed_at"]
                same_time = previous_observed == item["observed_at"]
                _, previous_reason = screen(previous["item"])
                _, current_reason = screen(item)
                current_is_terminal = current_reason in TERMINAL_SCREEN_REASONS
                previous_is_terminal = previous_reason in TERMINAL_SCREEN_REASONS
                if (previous_observed > item["observed_at"]
                        or (same_time and not (
                            current_is_terminal and not previous_is_terminal))):
                    rejection_by_index[index] = {
                        "index": index, "reason": "duplicate_older_or_equal",
                        "id": item["id"], "observed_at": item["observed_at"],
                        "payload_hash": record["payload_hash"]}
                    continue
            if previous:
                rejection_by_index[previous["index"]] = {
                    "index": previous["index"], "reason": "duplicate_superseded",
                    "id": item["id"],
                    "observed_at": previous["item"]["observed_at"],
                    "payload_hash": previous["payload_hash"]}
                records.remove(previous)
            by_id[item["id"]] = record
            records.append(record)
        except ValueError as exc:
            rejection_by_index[index] = {"index": index, "reason": str(exc)}

    for record in records:
        item = record["item"]
        eligible, reason = screen(item)
        if not eligible:
            rejection_by_index[record["index"]] = {
                "index": record["index"], "reason": reason, "id": item["id"],
                "observed_at": item["observed_at"],
                "expires_at": item["expires_at"],
                "payload_hash": record["payload_hash"]}
            continue
        try:
            item["score"], item["score_components"] = score(item)
            item["buyer_priority_rank"] = BUYER_STAGE_PRIORITY[
                item["buyer_stage"]]
            item["action_mode"] = action_mode(item)
            item["pipeline_state"] = ("payment_rail_blocked"
                                      if item["payment_rail_status"] == "temporarily_unavailable"
                                      else "qualified")
            item["source_index"] = record["index"]
            accepted.append(item)
        except ValueError as exc:
            rejection_by_index[record["index"]] = {
                "index": record["index"], "reason": str(exc)}
    accepted.sort(key=lambda item: (
        -item["buyer_priority_rank"], -item["score"],
        item["time_to_cash_days"], item["id"]))
    rejected = [rejection_by_index[index] for index in sorted(rejection_by_index)]
    for rejection in rejected:
        rejection.setdefault("payload_hash", payload_hash(payloads[rejection["index"]]))
    return {"metrics": {"received": len(payloads), "eligible": len(accepted), "rejected": len(rejected)},
            "opportunities": accepted, "rejections": rejected}

def open_ledger(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("""CREATE TABLE IF NOT EXISTS opportunities (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        score REAL NOT NULL,
        action_mode TEXT NOT NULL,
        pipeline_state TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS offer_phase_evidence (
        evidence_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        phase TEXT NOT NULL,
        reference TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        UNIQUE(opportunity_id, phase, reference)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS reusable_ip_assets (
        asset_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        name TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        maturity TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        UNIQUE(opportunity_id, asset_type, name)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS growth_evidence_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        payment_receipt_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('retention','expansion')),
        provider TEXT NOT NULL,
        external_event_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(payment_receipt_id) REFERENCES payment_receipts(receipt_id),
        UNIQUE(provider, kind, external_event_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recurring_growth_evidence_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        recurring_payment_receipt_id TEXT NOT NULL,
        recurring_economics_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('retention','expansion')),
        provider TEXT NOT NULL,
        external_event_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        prior_recurring_payment_receipt_id TEXT,
        baseline_scope TEXT,
        expanded_scope TEXT,
        baseline_value_cents INTEGER,
        expanded_value_cents INTEGER,
        occurred_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(recurring_payment_receipt_id)
          REFERENCES recurring_payment_receipts(receipt_id),
        FOREIGN KEY(recurring_economics_id)
          REFERENCES recurring_realized_unit_economics(economics_id),
        FOREIGN KEY(prior_recurring_payment_receipt_id)
          REFERENCES recurring_payment_receipts(receipt_id),
        UNIQUE(provider, kind, external_event_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS reusable_ip_reuse_receipts (
        receipt_id TEXT PRIMARY KEY,
        source_asset_id TEXT NOT NULL,
        source_opportunity_id TEXT NOT NULL,
        reused_asset_id TEXT NOT NULL,
        reused_opportunity_id TEXT NOT NULL,
        economics_kind TEXT NOT NULL CHECK(economics_kind IN ('one_time','recurring')),
        economics_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_event_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(source_asset_id) REFERENCES reusable_ip_assets(asset_id),
        FOREIGN KEY(source_opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(reused_asset_id) REFERENCES reusable_ip_assets(asset_id),
        FOREIGN KEY(reused_opportunity_id) REFERENCES opportunities(id),
        UNIQUE(provider, external_event_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS reusable_ip_promotions (
        promotion_id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        opportunity_id TEXT NOT NULL,
        from_maturity TEXT NOT NULL,
        to_maturity TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        promoted_at TEXT NOT NULL,
        FOREIGN KEY(asset_id) REFERENCES reusable_ip_assets(asset_id),
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        UNIQUE(asset_id, to_maturity)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS opportunity_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT,
        decision TEXT NOT NULL,
        reason TEXT NOT NULL,
        source_index INTEGER NOT NULL,
        payload_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS opportunity_transitions (
        transition_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        from_state TEXT NOT NULL,
        to_state TEXT NOT NULL,
        evidence_id TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS proposal_artifacts (
        proposal_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        artifact_hash TEXT NOT NULL,
        artifact_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        UNIQUE(opportunity_id, artifact_hash)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recurring_pricing_terms (
        term_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL UNIQUE,
        base_fee_cents INTEGER NOT NULL,
        billing_cadence TEXT NOT NULL,
        included_services_json TEXT NOT NULL,
        included_usage_definition TEXT NOT NULL,
        support_boundaries TEXT NOT NULL,
        exception_boundaries TEXT NOT NULL,
        renewal_terms TEXT NOT NULL,
        termination_terms TEXT NOT NULL,
        terms_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(proposal_id) REFERENCES proposal_artifacts(proposal_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS submission_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_submission_id TEXT NOT NULL,
        submission_url TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(proposal_id) REFERENCES proposal_artifacts(proposal_id),
        UNIQUE(provider, external_submission_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS response_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        submission_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_message_id TEXT NOT NULL,
        message_url TEXT NOT NULL,
        received_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(submission_receipt_id) REFERENCES submission_receipts(receipt_id),
        UNIQUE(provider, external_message_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS contract_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        response_receipt_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_contract_id TEXT NOT NULL,
        contract_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        contracted_at TEXT NOT NULL,
        terms_authority TEXT NOT NULL,
        authority_evidence_url TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(response_receipt_id) REFERENCES response_receipts(receipt_id),
        FOREIGN KEY(proposal_id) REFERENCES proposal_artifacts(proposal_id),
        UNIQUE(provider, external_contract_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS contract_recurring_terms (
        contract_receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        term_id TEXT NOT NULL,
        accepted_terms_hash TEXT NOT NULL,
        accepted_base_fee_cents INTEGER NOT NULL,
        acceptance_evidence_url TEXT NOT NULL,
        accepted_at TEXT NOT NULL,
        binding_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(contract_receipt_id) REFERENCES contract_receipts(receipt_id),
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(term_id) REFERENCES recurring_pricing_terms(term_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recurring_payment_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        contract_receipt_id TEXT NOT NULL,
        term_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_invoice_id TEXT NOT NULL,
        invoice_url TEXT NOT NULL,
        external_transaction_id TEXT NOT NULL,
        transaction_url TEXT NOT NULL,
        gross_amount_cents INTEGER NOT NULL,
        fee_amount_cents INTEGER NOT NULL,
        net_amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        service_period_start TEXT NOT NULL,
        service_period_end TEXT NOT NULL,
        invoiced_at TEXT NOT NULL,
        paid_at TEXT NOT NULL,
        settled_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(contract_receipt_id)
          REFERENCES contract_recurring_terms(contract_receipt_id),
        FOREIGN KEY(term_id) REFERENCES recurring_pricing_terms(term_id),
        UNIQUE(provider, external_invoice_id),
        UNIQUE(provider, external_transaction_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS execution_plans (
        plan_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        contract_receipt_id TEXT NOT NULL,
        plan_hash TEXT NOT NULL,
        plan_json TEXT NOT NULL,
        started_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(contract_receipt_id) REFERENCES contract_receipts(receipt_id),
        UNIQUE(opportunity_id, plan_hash)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS qa_reports (
        report_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        execution_plan_id TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        report_hash TEXT NOT NULL,
        report_json TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(execution_plan_id) REFERENCES execution_plans(plan_id),
        UNIQUE(opportunity_id, report_hash)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS delivery_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        qa_report_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_delivery_id TEXT NOT NULL,
        delivery_url TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        delivered_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(qa_report_id) REFERENCES qa_reports(report_id),
        UNIQUE(provider, external_delivery_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS outcome_pricing_terms (
        term_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL UNIQUE,
        success_definition TEXT NOT NULL,
        attribution_method TEXT NOT NULL,
        exclusions_json TEXT NOT NULL,
        fee_cap_cents INTEGER NOT NULL,
        human_escalation_rule TEXT NOT NULL,
        terms_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS contract_outcome_terms (
        contract_receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        term_id TEXT NOT NULL,
        accepted_terms_hash TEXT NOT NULL,
        accepted_fee_cap_cents INTEGER NOT NULL,
        acceptance_evidence_url TEXT NOT NULL,
        accepted_at TEXT NOT NULL,
        binding_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(contract_receipt_id) REFERENCES contract_receipts(receipt_id),
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(term_id) REFERENCES outcome_pricing_terms(term_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS attributed_outcome_events (
        event_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        term_id TEXT NOT NULL,
        contract_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_event_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        attribution_reference TEXT NOT NULL,
        eligibility_review_json TEXT NOT NULL,
        units INTEGER NOT NULL,
        unit_fee_cents INTEGER NOT NULL,
        fee_cents INTEGER NOT NULL,
        occurred_at TEXT NOT NULL,
        event_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(term_id) REFERENCES outcome_pricing_terms(term_id),
        FOREIGN KEY(contract_receipt_id) REFERENCES contract_receipts(receipt_id),
        UNIQUE(provider, external_event_id)
    )""")
    outcome_event_columns = {
        row[1] for row in connection.execute(
            "PRAGMA table_info(attributed_outcome_events)").fetchall()
    }
    if "eligibility_review_json" not in outcome_event_columns:
        connection.execute(
            "ALTER TABLE attributed_outcome_events "
            "ADD COLUMN eligibility_review_json TEXT")
    if "artifact_sha256" not in outcome_event_columns:
        connection.execute(
            "ALTER TABLE attributed_outcome_events "
            "ADD COLUMN artifact_sha256 TEXT")
    connection.execute("""CREATE TABLE IF NOT EXISTS invoice_outcome_events (
        invoice_receipt_id TEXT NOT NULL,
        event_id TEXT NOT NULL UNIQUE,
        outcome_fee_cents INTEGER NOT NULL,
        PRIMARY KEY(invoice_receipt_id,event_id),
        FOREIGN KEY(invoice_receipt_id) REFERENCES invoice_receipts(receipt_id),
        FOREIGN KEY(event_id) REFERENCES attributed_outcome_events(event_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS invoice_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        delivery_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_invoice_id TEXT NOT NULL,
        invoice_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        issued_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(delivery_receipt_id) REFERENCES delivery_receipts(receipt_id),
        UNIQUE(provider, external_invoice_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS payment_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        invoice_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_transaction_id TEXT NOT NULL,
        transaction_url TEXT NOT NULL,
        gross_amount_cents INTEGER NOT NULL,
        fee_amount_cents INTEGER NOT NULL,
        net_amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        paid_at TEXT NOT NULL,
        settled_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(invoice_receipt_id) REFERENCES invoice_receipts(receipt_id),
        UNIQUE(provider, external_transaction_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS realized_unit_economics (
        economics_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        payment_receipt_id TEXT NOT NULL UNIQUE,
        net_collected_cents INTEGER NOT NULL,
        delivery_cost_cents INTEGER NOT NULL,
        inference_cost_cents INTEGER NOT NULL,
        cac_cents INTEGER NOT NULL,
        human_operating_minutes INTEGER NOT NULL,
        contribution_cents INTEGER NOT NULL,
        contribution_margin REAL NOT NULL,
        revenue_per_human_hour REAL NOT NULL,
        contribution_per_human_hour REAL NOT NULL,
        currency TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        measured_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(payment_receipt_id) REFERENCES payment_receipts(receipt_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recurring_realized_unit_economics (
        economics_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        recurring_payment_receipt_id TEXT NOT NULL UNIQUE,
        net_collected_cents INTEGER NOT NULL,
        delivery_cost_cents INTEGER NOT NULL,
        inference_cost_cents INTEGER NOT NULL,
        cac_cents INTEGER NOT NULL,
        human_operating_minutes INTEGER NOT NULL,
        contribution_cents INTEGER NOT NULL,
        contribution_margin REAL NOT NULL,
        revenue_per_human_hour REAL NOT NULL,
        contribution_per_human_hour REAL NOT NULL,
        currency TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        evidence_hash TEXT NOT NULL,
        measured_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(recurring_payment_receipt_id)
          REFERENCES recurring_payment_receipts(receipt_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recurring_payout_availability_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        recurring_payment_receipt_id TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        external_balance_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        available_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(recurring_payment_receipt_id)
          REFERENCES recurring_payment_receipts(receipt_id),
        UNIQUE(provider, external_balance_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recurring_bank_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        recurring_payout_receipt_id TEXT NOT NULL UNIQUE,
        financial_institution TEXT NOT NULL,
        external_transfer_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        received_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(recurring_payout_receipt_id)
          REFERENCES recurring_payout_availability_receipts(receipt_id),
        UNIQUE(financial_institution, external_transfer_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS payout_availability_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        payment_receipt_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        external_balance_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        available_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(payment_receipt_id) REFERENCES payment_receipts(receipt_id),
        UNIQUE(provider, external_balance_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS bank_receipts (
        receipt_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        payout_availability_receipt_id TEXT NOT NULL,
        financial_institution TEXT NOT NULL,
        external_transfer_id TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        received_at TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(payout_availability_receipt_id)
            REFERENCES payout_availability_receipts(receipt_id),
        UNIQUE(financial_institution, external_transfer_id)
    )""")
    return connection


def receipt_id(opportunity_id, decision, reason, source_index, digest):
    value = f"{opportunity_id or ''}|{decision}|{reason}|{source_index}|{digest}"
    return "oppr_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def transition_id(opportunity_id, from_state, to_state, evidence_id):
    value = f"{opportunity_id}|{from_state}|{to_state}|{evidence_id}"
    return "oppt_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def _proposal_text(value, field, maximum):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{field}_too_long")
    return value


def prepare_proposal(path, opportunity_id, proposal, *, now=None):
    """Persist a truthful proposal and advance qualified work atomically.

    Claims are optional, but every included claim needs an HTTPS evidence source
    and an explicit verification timestamp. This prepares a proposal only; it
    never submits, contacts, contracts, invoices, or charges.
    """
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(proposal, dict):
        raise ValueError("proposal_object_required")
    opportunity_id = opportunity_id.strip()
    scope = _proposal_text(proposal.get("scope"), "scope", 2000)
    price_cents = finite_number(proposal, "price_cents", minimum=1)
    if not price_cents.is_integer():
        raise ValueError("price_cents_invalid")
    milestones = proposal.get("milestones")
    if not isinstance(milestones, list) or not 1 <= len(milestones) <= 8:
        raise ValueError("milestones_invalid")
    normalized_milestones = []
    milestone_total = 0
    for milestone in milestones:
        if not isinstance(milestone, dict):
            raise ValueError("milestone_invalid")
        title = _proposal_text(milestone.get("title"), "milestone_title", 160)
        deliverable = _proposal_text(milestone.get("deliverable"), "milestone_deliverable", 1000)
        amount = finite_number(milestone, "amount_cents", minimum=1)
        days = finite_number(milestone, "due_days", minimum=1, maximum=365)
        if not amount.is_integer() or not days.is_integer():
            raise ValueError("milestone_number_invalid")
        milestone_total += int(amount)
        stage_id = str(milestone.get("stage_id") or "").strip().lower() or None
        if stage_id is not None and stage_id not in {
                "diagnostic_pilot", "implementation"}:
            raise ValueError("milestone_offer_stage_invalid")
        raw_criteria = milestone.get("acceptance_criteria", [])
        if not isinstance(raw_criteria, list) or len(raw_criteria) > 20:
            raise ValueError("milestone_acceptance_criteria_invalid")
        criteria = []
        for criterion in raw_criteria:
            if not isinstance(criterion, str) or not criterion.strip():
                raise ValueError("milestone_acceptance_criterion_invalid")
            normalized_criterion = criterion.strip()
            if len(normalized_criterion) > 500:
                raise ValueError("milestone_acceptance_criterion_too_long")
            if normalized_criterion not in criteria:
                criteria.append(normalized_criterion)
        normalized_milestones.append({
            "title": title, "deliverable": deliverable,
            "amount_cents": int(amount), "due_days": int(days),
            "stage_id": stage_id, "acceptance_criteria": criteria})
    if milestone_total != int(price_cents):
        raise ValueError("milestone_total_mismatch")
    recurring_base_fee_cents = finite_number(
        proposal, "recurring_base_fee_cents", minimum=0, required=False)
    recurring_base_fee_cents = recurring_base_fee_cents or 0
    if not recurring_base_fee_cents.is_integer():
        raise ValueError("recurring_base_fee_cents_invalid")
    if proposal.get("outcome_fee_cents") is not None:
        raise ValueError("outcome_fee_must_remain_variable_and_capped")
    recurring_terms = normalize_recurring_terms(
        proposal, int(recurring_base_fee_cents))

    claims = proposal.get("claims", [])
    if not isinstance(claims, list) or len(claims) > 20:
        raise ValueError("claims_invalid")
    normalized_claims = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("claim_invalid")
        text = _proposal_text(claim.get("text"), "claim_text", 500)
        source_url = canonical_url(
            _proposal_text(claim.get("source_url"), "claim_source_url", 2000))
        if urlsplit(source_url).scheme != "https":
            raise ValueError("claim_source_url_https_required")
        verified_at = parse_time(claim.get("verified_at"), "claim_verified_at")
        recorded_at = now or utc_now()
        if verified_at > recorded_at + MAX_FUTURE_SKEW:
            raise ValueError("claim_verified_at_future")
        normalized_claims.append({"text": text, "source_url": source_url,
                                  "verified_at": verified_at.isoformat()})

    artifact = {"opportunity_id": opportunity_id, "scope": scope,
                "price_cents": int(price_cents), "milestones": normalized_milestones,
                "recurring_base_fee_cents": int(recurring_base_fee_cents),
                "recurring_terms": recurring_terms,
                "claims": normalized_claims}
    created_at = (now or utc_now()).isoformat()
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            opportunity = json.loads(row[1])
            proposal_economics = {
                "basis": "proposal_price",
                "evidence_status": "cost_estimates_incomplete",
                "price_cents": int(price_cents),
            }
            if opportunity.get("cost_estimates_complete"):
                projected_cost_cents = sum(
                    opportunity[field]
                    for field in (
                        "delivery_cost_cents",
                        "inference_cost_cents",
                        "cac_cents",
                    )
                )
                projected_contribution_cents = (
                    int(price_cents) - projected_cost_cents
                )
                if projected_contribution_cents <= 0:
                    raise ValueError(
                        "proposal_non_positive_projected_contribution"
                    )
                effort_hours = opportunity["effort_hours"]
                proposal_economics.update({
                    "evidence_status": "projected_not_collected",
                    "delivery_cost_cents": opportunity["delivery_cost_cents"],
                    "inference_cost_cents": opportunity["inference_cost_cents"],
                    "cac_cents": opportunity["cac_cents"],
                    "total_cost_cents": projected_cost_cents,
                    "projected_contribution_cents": projected_contribution_cents,
                    "projected_contribution_margin": round(
                        projected_contribution_cents / int(price_cents), 6),
                    "required_human_hours": effort_hours,
                    "projected_contribution_per_human_hour_cents": round(
                        projected_contribution_cents / effort_hours, 2),
                })
            artifact["proposal_unit_economics"] = proposal_economics
            selection = opportunity.get("offer_family_selection") or {}
            artifact["offer_family"] = ({
                "id": selection.get("id"),
                "catalog_version": selection.get("catalog_version"),
                "asset_hash": selection.get("asset_hash"),
                "fit_score": selection.get("fit_score"),
                "qualification": selection.get("qualification", {}),
                "evidence": selection.get("evidence", []),
                "maturity": selection.get("maturity"),
            } if selection.get("id") else None)
            artifact["offer_architecture"] = derive_offer_architecture(
                opportunity, int(price_cents), normalized_milestones)
            artifact["pricing_composition"] = validate_offer_pricing(
                artifact["offer_architecture"], normalized_milestones,
                int(price_cents), int(recurring_base_fee_cents), recurring_terms)
            serialized = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
            artifact_hash = hashlib.sha256(serialized.encode()).hexdigest()
            proposal_id = "prop_" + artifact_hash[:24]
            evidence_id = "proposal:" + proposal_id
            existing = connection.execute(
                "SELECT 1 FROM proposal_artifacts WHERE proposal_id=?",
                (proposal_id,)).fetchone()
            if row[0] == "proposal_ready" and existing:
                return {"proposal_id": proposal_id, "changed": False, "state": row[0]}
            if row[0] != "qualified":
                raise ValueError("pipeline_state_conflict")
            if artifact["price_cents"] > opportunity["payout_cents"]:
                raise ValueError("price_exceeds_opportunity_payout")
            tid = transition_id(opportunity_id, "qualified", "proposal_ready", evidence_id)
            con…22992 tokens truncated…             evidence["proposal_projection_comparison"] = {
                    "proposal_id": proposal_id,
                    "projected_contribution_cents": projected[
                        "projected_contribution_cents"],
                    "realized_contribution_cents": contribution,
                    "contribution_variance_cents": (
                        contribution
                        - projected["projected_contribution_cents"]),
                    "projected_contribution_margin": projected[
                        "projected_contribution_margin"],
                    "realized_contribution_margin": round(margin, 6),
                }
            normalized = {
                "opportunity_id": opportunity_id,
                "payment_receipt_id": payment_receipt_id,
                "net_collected_cents": net_collected,
                **costs,
                "human_operating_minutes": minutes,
                "contribution_cents": contribution,
                "contribution_margin": round(margin, 6),
                "revenue_per_human_hour": round(revenue_per_hour, 2),
                "contribution_per_human_hour": round(contribution_per_hour, 2),
                "currency": payment[8],
                "evidence": evidence,
                "measured_at": measured_at.isoformat(),
                "evidence_status": "realized_from_settled_payment",
            }
            serialized = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            evidence_hash = hashlib.sha256(serialized.encode()).hexdigest()
            economics_id = "ruec_" + evidence_hash[:24]
            existing = connection.execute(
                """SELECT economics_id FROM realized_unit_economics
                   WHERE payment_receipt_id=?""",
                (payment_receipt_id,)).fetchone()
            if existing:
                if existing[0] != economics_id:
                    raise ValueError("realized_economics_conflict")
                return {"economics_id": economics_id, "changed": False, **normalized}
            recorded_at = recorded.isoformat()
            connection.execute(
                """INSERT INTO realized_unit_economics
                   (economics_id,opportunity_id,payment_receipt_id,
                    net_collected_cents,delivery_cost_cents,inference_cost_cents,
                    cac_cents,human_operating_minutes,contribution_cents,
                    contribution_margin,revenue_per_human_hour,
                    contribution_per_human_hour,currency,evidence_json,
                    evidence_hash,measured_at,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (economics_id, opportunity_id, payment_receipt_id,
                 net_collected, costs["delivery_cost_cents"],
                 costs["inference_cost_cents"], costs["cac_cents"], minutes,
                 contribution, round(margin, 6), round(revenue_per_hour, 2),
                 round(contribution_per_hour, 2), payment[8],
                 json.dumps(evidence, sort_keys=True, separators=(",", ":")),
                 evidence_hash, measured_at.isoformat(), recorded_at))
        return {"economics_id": economics_id, "changed": True, **normalized}
    finally:
        connection.close()


def _verified_recurring_payment_receipt(
        connection, recurring_payment_receipt_id):
    """Return recurring payment evidence only when its snapshot matches."""
    payment = connection.execute(
        """SELECT opportunity_id,contract_receipt_id,term_id,provider,
                  external_invoice_id,invoice_url,external_transaction_id,
                  transaction_url,gross_amount_cents,fee_amount_cents,
                  net_amount_cents,currency,service_period_start,
                  service_period_end,invoiced_at,paid_at,settled_at,receipt_hash
           FROM recurring_payment_receipts WHERE receipt_id=?""",
        (recurring_payment_receipt_id,)).fetchone()
    if payment is None:
        raise ValueError("recurring_payment_receipt_not_found")
    snapshot = {
        "opportunity_id": payment[0],
        "contract_receipt_id": payment[1],
        "term_id": payment[2],
        "provider": payment[3],
        "external_invoice_id": payment[4],
        "invoice_url": payment[5],
        "external_transaction_id": payment[6],
        "transaction_url": payment[7],
        "gross_amount_cents": payment[8],
        "fee_amount_cents": payment[9],
        "net_amount_cents": payment[10],
        "currency": payment[11],
        "service_period_start": payment[12],
        "service_period_end": payment[13],
        "invoiced_at": payment[14],
        "paid_at": payment[15],
        "settled_at": payment[16],
    }
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    try:
        period_start = parse_time(payment[12], "service_period_start")
        period_end = parse_time(payment[13], "service_period_end")
        invoiced_at = parse_time(payment[14], "invoiced_at")
        paid_at = parse_time(payment[15], "paid_at")
        settled_at = parse_time(payment[16], "settled_at")
        amounts_valid = (
            all(isinstance(payment[index], int)
                and not isinstance(payment[index], bool)
                for index in (8, 9, 10))
            and payment[8] > 0
            and payment[9] >= 0
            and payment[10] > 0
            and payment[10] == payment[8] - payment[9]
        )
        semantics_valid = (
            amounts_valid
            and re.fullmatch(r"[A-Z]{3}", str(payment[11] or "")) is not None
            and urlsplit(str(payment[5] or "")).scheme == "https"
            and urlsplit(str(payment[7] or "")).scheme == "https"
            and period_start < period_end
            and invoiced_at <= paid_at <= settled_at
            and settled_at <= utc_now() + MAX_FUTURE_SKEW
        )
    except (TypeError, ValueError):
        semantics_valid = False
    if (payment[17] != expected_hash
            or recurring_payment_receipt_id != (
                "recurpay_" + expected_hash[:24])
            or not semantics_valid):
        raise ValueError("recurring_payment_receipt_unverified")
    return payment


def _verified_realized_economics(connection, economics_id, *, recurring=False):
    """Rebuild and verify an immutable realized-economics snapshot."""
    table = (
        "recurring_realized_unit_economics"
        if recurring else "realized_unit_economics"
    )
    receipt_column = (
        "recurring_payment_receipt_id" if recurring else "payment_receipt_id"
    )
    row = connection.execute(
        f"""SELECT opportunity_id,{receipt_column},net_collected_cents,
                   delivery_cost_cents,inference_cost_cents,cac_cents,
                   human_operating_minutes,contribution_cents,
                   contribution_margin,revenue_per_human_hour,
                   contribution_per_human_hour,currency,evidence_json,
                   evidence_hash,measured_at
            FROM {table} WHERE economics_id=?""",
        (economics_id,),
    ).fetchone()
    missing = (
        "recurring_realized_economics_not_found"
        if recurring else "realized_economics_not_found"
    )
    if row is None:
        raise ValueError(missing)
    try:
        evidence = json.loads(row[12])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("realized_economics_unverified") from exc
    if not isinstance(evidence, dict):
        raise ValueError("realized_economics_unverified")
    normalized = {
        "opportunity_id": row[0],
        receipt_column: row[1],
        "net_collected_cents": row[2],
        "delivery_cost_cents": row[3],
        "inference_cost_cents": row[4],
        "cac_cents": row[5],
        "human_operating_minutes": row[6],
        "contribution_cents": row[7],
        "contribution_margin": row[8],
        "revenue_per_human_hour": row[9],
        "contribution_per_human_hour": row[10],
        "currency": row[11],
        "evidence": evidence,
        "measured_at": row[14],
        "evidence_status": (
            "realized_from_settled_recurring_payment"
            if recurring else "realized_from_settled_payment"
        ),
    }
    serialized = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    prefix = "rruec_" if recurring else "ruec_"
    if row[13] != expected_hash or economics_id != prefix + expected_hash[:24]:
        raise ValueError("realized_economics_unverified")
    try:
        payment = (
            _verified_recurring_payment_receipt(connection, row[1])
            if recurring else _verified_payment_receipt(connection, row[1])
        )
    except ValueError as exc:
        raise ValueError("realized_economics_unverified") from exc
    payment_net_index = 10 if recurring else 7
    payment_currency_index = 11 if recurring else 8
    payment_settled_index = 16 if recurring else 10
    if (
        payment[0] != row[0]
        or payment[payment_net_index] != row[2]
        or payment[payment_currency_index] != row[11]
        or parse_time(row[14], "economics_measured_at")
        < parse_time(payment[payment_settled_index], "payment_settled_at")
        or row[2] <= 0
        or row[6] <= 0
    ):
        raise ValueError("realized_economics_unverified")
    expected_contribution = row[2] - row[3] - row[4] - row[5]
    hours = row[6] / 60
    derived = (
        expected_contribution,
        round(expected_contribution / row[2], 6),
        round(row[2] / 100 / hours, 2),
        round(expected_contribution / 100 / hours, 2),
    )
    if derived != (row[7], row[8], row[9], row[10]):
        raise ValueError("realized_economics_unverified")
    if not recurring:
        try:
            proposal_id, proposal = _verified_linked_proposal_for_payment(
                connection, payment)
        except ValueError as exc:
            raise ValueError("realized_economics_unverified") from exc
        projected = proposal.get("proposal_unit_economics") or {}
        comparison = evidence.get("proposal_projection_comparison")
        expected_comparison = None
        if projected.get("evidence_status") == "projected_not_collected":
            expected_comparison = {
                "proposal_id": proposal_id,
                "projected_contribution_cents":
                    projected["projected_contribution_cents"],
                "realized_contribution_cents": row[7],
                "contribution_variance_cents": (
                    row[7] - projected["projected_contribution_cents"]),
                "projected_contribution_margin":
                    projected["projected_contribution_margin"],
                "realized_contribution_margin": row[8],
            }
        if comparison != expected_comparison:
            raise ValueError("realized_economics_unverified")
    return {
        "opportunity_id": row[0],
        "payment_receipt_id": row[1],
        "contribution_cents": row[7],
        "measured_at": row[14],
    }


def summarize_verified_forecast_accuracy(path):
    """Aggregate proposal forecast accuracy from reverified settled economics."""
    connection = open_ledger(path)
    try:
        economics_ids = [
            row[0] for row in connection.execute(
                """SELECT economics_id FROM realized_unit_economics
                   ORDER BY measured_at,economics_id"""
            ).fetchall()
        ]
        by_currency = {}
        verified_count = 0
        for economics_id in economics_ids:
            _verified_realized_economics(connection, economics_id)
            row = connection.execute(
                """SELECT currency,evidence_json
                   FROM realized_unit_economics WHERE economics_id=?""",
                (economics_id,),
            ).fetchone()
            evidence = json.loads(row[1])
            comparison = evidence.get("proposal_projection_comparison")
            if comparison is None:
                continue
            verified_count += 1
            bucket = by_currency.setdefault(row[0], {
                "comparison_count": 0,
                "projected_contribution_cents": 0,
                "realized_contribution_cents": 0,
                "net_variance_cents": 0,
                "absolute_error_cents": 0,
            })
            variance = comparison["contribution_variance_cents"]
            bucket["comparison_count"] += 1
            bucket["projected_contribution_cents"] += (
                comparison["projected_contribution_cents"])
            bucket["realized_contribution_cents"] += (
                comparison["realized_contribution_cents"])
            bucket["net_variance_cents"] += variance
            bucket["absolute_error_cents"] += abs(variance)
        for bucket in by_currency.values():
            bucket["mean_absolute_error_cents"] = round(
                bucket.pop("absolute_error_cents")
                / bucket["comparison_count"],
                2,
            )
        return {
            "verified_comparison_count": verified_count,
            "by_currency": by_currency,
            "status": "verified_settled_forecast_accuracy",
        }
    finally:
        connection.close()


def _verified_recurring_growth_evidence(connection, receipt_id):
    """Rebuild a recurring growth receipt and its settled economics lineage."""
    row = connection.execute(
        """SELECT opportunity_id,recurring_payment_receipt_id,
                  recurring_economics_id,kind,provider,external_event_id,
                  evidence_url,prior_recurring_payment_receipt_id,
                  baseline_scope,expanded_scope,baseline_value_cents,
                  expanded_value_cents,occurred_at,receipt_hash
           FROM recurring_growth_evidence_receipts WHERE receipt_id=?""",
        (receipt_id,),
    ).fetchone()
    if row is None:
        raise ValueError("recurring_growth_evidence_receipt_not_found")
    normalized = {
        "opportunity_id": row[0],
        "recurring_payment_receipt_id": row[1],
        "kind": row[3],
        "provider": row[4],
        "external_event_id": row[5],
        "evidence_url": row[6],
        "occurred_at": row[12],
        "recurring_economics_id": row[2],
    }
    if row[3] == "retention":
        normalized["prior_recurring_payment_receipt_id"] = row[7]
    elif row[3] == "expansion":
        normalized.update({
            "baseline_scope": row[8],
            "expanded_scope": row[9],
            "baseline_value_cents": row[10],
            "expanded_value_cents": row[11],
        })
    else:
        raise ValueError("recurring_growth_evidence_unverified")
    serialized = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    if row[13] != expected_hash or receipt_id != (
            "rgrow_" + expected_hash[:24]):
        raise ValueError("recurring_growth_evidence_unverified")
    try:
        payment = _verified_recurring_payment_receipt(connection, row[1])
        economics = _verified_realized_economics(
            connection, row[2], recurring=True)
        prior = (
            _verified_recurring_payment_receipt(connection, row[7])
            if row[3] == "retention" else None)
    except ValueError as exc:
        raise ValueError("recurring_growth_evidence_unverified") from exc
    if (
        payment[0] != row[0]
        or economics["opportunity_id"] != row[0]
        or economics["payment_receipt_id"] != row[1]
        or economics["contribution_cents"] <= 0
        or parse_time(row[12], "growth_occurred_at")
           < parse_time(payment[16], "recurring_settled_at")
        or (prior is not None and prior[0] != row[0])
    ):
        raise ValueError("recurring_growth_evidence_unverified")
    return normalized


def record_recurring_withdrawable_balance(
        path, opportunity_id, recurring_payment_receipt_id, evidence, *, now=None):
    """Record provider evidence that settled recurring net is withdrawable."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if (not isinstance(recurring_payment_receipt_id, str)
            or not recurring_payment_receipt_id.strip()):
        raise ValueError("recurring_payment_receipt_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("recurring_withdrawable_evidence_object_required")
    opportunity_id = opportunity_id.strip()
    recurring_payment_receipt_id = recurring_payment_receipt_id.strip()
    provider = _proposal_text(
        evidence.get("provider"), "withdrawable_provider", 160)
    external_id = _proposal_text(
        evidence.get("external_balance_id"), "external_balance_id", 500)
    evidence_url = canonical_url(_proposal_text(
        evidence.get("evidence_url"), "withdrawable_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("withdrawable_evidence_url_https_required")
    amount = finite_number(evidence, "amount_cents", minimum=1)
    if not amount.is_integer():
        raise ValueError("amount_cents_invalid")
    amount_cents = int(amount)
    currency = _proposal_text(
        evidence.get("currency"), "withdrawable_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("withdrawable_currency_invalid")
    available_at = parse_time(evidence.get("available_at"), "available_at")
    recorded = now or utc_now()
    if available_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("available_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            payment = _verified_recurring_payment_receipt(
                connection, recurring_payment_receipt_id)
            if payment[0] != opportunity_id:
                raise ValueError("recurring_withdrawable_opportunity_mismatch")
            if payment[3].casefold() != provider.casefold():
                raise ValueError("recurring_withdrawable_provider_mismatch")
            if payment[10] != amount_cents:
                raise ValueError("recurring_withdrawable_amount_mismatch")
            if payment[11] != currency:
                raise ValueError("recurring_withdrawable_currency_mismatch")
            if available_at < parse_time(payment[16], "payment_settled_at"):
                raise ValueError("recurring_withdrawable_before_settlement")
            normalized = {
                "opportunity_id": opportunity_id,
                "recurring_payment_receipt_id":
                    recurring_payment_receipt_id,
                "provider": provider,
                "external_balance_id": external_id,
                "evidence_url": evidence_url,
                "amount_cents": amount_cents,
                "currency": currency,
                "available_at": available_at.isoformat(),
            }
            serialized = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "recuravail_" + receipt_hash[:24]
            existing = connection.execute(
                """SELECT receipt_id,receipt_hash
                   FROM recurring_payout_availability_receipts
                   WHERE recurring_payment_receipt_id=?
                      OR (provider=? AND external_balance_id=?)""",
                (recurring_payment_receipt_id, provider,
                 external_id)).fetchone()
            if existing:
                if existing[1] != receipt_hash:
                    raise ValueError(
                        "recurring_withdrawable_evidence_conflict")
                return {
                    "receipt_id": existing[0], "changed": False,
                    "status": "recurring_withdrawable_verified",
                    "amount_cents": amount_cents}
            connection.execute(
                """INSERT INTO recurring_payout_availability_receipts
                   (receipt_id,opportunity_id,recurring_payment_receipt_id,
                    provider,external_balance_id,evidence_url,amount_cents,
                    currency,available_at,receipt_hash,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id,
                    recurring_payment_receipt_id, provider, external_id,
                    evidence_url, amount_cents, currency,
                    available_at.isoformat(), receipt_hash,
                    recorded.isoformat()))
            return {
                "receipt_id": receipt_id, "changed": True,
                "status": "recurring_withdrawable_verified",
                "amount_cents": amount_cents}
    finally:
        connection.close()


def _verified_recurring_payout_receipt(
        connection, recurring_payout_receipt_id):
    """Return recurring payout evidence only when its snapshot matches."""
    payout = connection.execute(
        """SELECT opportunity_id,recurring_payment_receipt_id,provider,
                  external_balance_id,evidence_url,amount_cents,currency,
                  available_at,receipt_hash
           FROM recurring_payout_availability_receipts WHERE receipt_id=?""",
        (recurring_payout_receipt_id,)).fetchone()
    if payout is None:
        raise ValueError("recurring_payout_receipt_not_found")
    snapshot = {
        "opportunity_id": payout[0],
        "recurring_payment_receipt_id": payout[1],
        "provider": payout[2],
        "external_balance_id": payout[3],
        "evidence_url": payout[4],
        "amount_cents": payout[5],
        "currency": payout[6],
        "available_at": payout[7],
    }
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    try:
        provider = _proposal_text(
            payout[2], "withdrawable_provider", 160)
        external_id = _proposal_text(
            payout[3], "external_balance_id", 500)
        evidence_url = canonical_url(_proposal_text(
            payout[4], "withdrawable_evidence_url", 2000))
        available_at = parse_time(payout[7], "available_at")
        semantics_valid = (
            provider == payout[2]
            and external_id == payout[3]
            and evidence_url == payout[4]
            and urlsplit(evidence_url).scheme == "https"
            and isinstance(payout[5], int)
            and not isinstance(payout[5], bool)
            and payout[5] > 0
            and re.fullmatch(r"[A-Z]{3}", str(payout[6] or "")) is not None
            and available_at <= utc_now() + MAX_FUTURE_SKEW
        )
    except (TypeError, ValueError):
        semantics_valid = False
    if (payout[8] != expected_hash
            or recurring_payout_receipt_id != (
                "recuravail_" + expected_hash[:24])
            or not semantics_valid):
        raise ValueError("recurring_payout_receipt_unverified")
    return payout


def _verified_recurring_bank_receipt(connection, recurring_bank_receipt_id):
    """Return recurring bank evidence only when its snapshot matches."""
    bank = connection.execute(
        """SELECT opportunity_id,recurring_payout_receipt_id,
                  financial_institution,external_transfer_id,evidence_url,
                  amount_cents,currency,received_at,receipt_hash
           FROM recurring_bank_receipts WHERE receipt_id=?""",
        (recurring_bank_receipt_id,)).fetchone()
    if bank is None:
        raise ValueError("recurring_bank_receipt_not_found")
    snapshot = {
        "opportunity_id": bank[0],
        "recurring_payout_receipt_id": bank[1],
        "financial_institution": bank[2],
        "external_transfer_id": bank[3],
        "evidence_url": bank[4],
        "amount_cents": bank[5],
        "currency": bank[6],
        "received_at": bank[7],
    }
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    try:
        institution = _proposal_text(
            bank[2], "financial_institution", 160)
        external_id = _proposal_text(
            bank[3], "external_transfer_id", 500)
        evidence_url = canonical_url(_proposal_text(
            bank[4], "bank_evidence_url", 2000))
        received_at = parse_time(bank[7], "received_at")
        semantics_valid = (
            institution == bank[2]
            and external_id == bank[3]
            and evidence_url == bank[4]
            and urlsplit(evidence_url).scheme == "https"
            and isinstance(bank[5], int)
            and not isinstance(bank[5], bool)
            and bank[5] > 0
            and re.fullmatch(r"[A-Z]{3}", str(bank[6] or "")) is not None
            and received_at <= utc_now() + MAX_FUTURE_SKEW
        )
    except (TypeError, ValueError):
        semantics_valid = False
    if (bank[8] != expected_hash
            or recurring_bank_receipt_id != (
                "recurbank_" + expected_hash[:24])
            or not semantics_valid):
        raise ValueError("recurring_bank_receipt_unverified")
    return bank


def record_recurring_bank_receipt(
        path, opportunity_id, recurring_payout_receipt_id, evidence, *, now=None):
    """Record proof that recurring withdrawable funds reached the bank."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if (not isinstance(recurring_payout_receipt_id, str)
            or not recurring_payout_receipt_id.strip()):
        raise ValueError("recurring_payout_receipt_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("recurring_bank_receipt_object_required")
    opportunity_id = opportunity_id.strip()
    recurring_payout_receipt_id = recurring_payout_receipt_id.strip()
    institution = _proposal_text(
        evidence.get("financial_institution"), "financial_institution", 160)
    external_id = _proposal_text(
        evidence.get("external_transfer_id"), "external_transfer_id", 500)
    evidence_url = canonical_url(_proposal_text(
        evidence.get("evidence_url"), "bank_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("bank_evidence_url_https_required")
    amount = finite_number(evidence, "amount_cents", minimum=1)
    if not amount.is_integer():
        raise ValueError("amount_cents_invalid")
    amount_cents = int(amount)
    currency = _proposal_text(
        evidence.get("currency"), "bank_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("bank_currency_invalid")
    received_at = parse_time(evidence.get("received_at"), "received_at")
    recorded = now or utc_now()
    if received_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("received_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            payout = _verified_recurring_payout_receipt(
                connection, recurring_payout_receipt_id)
            if payout[0] != opportunity_id:
                raise ValueError("recurring_bank_opportunity_mismatch")
            if payout[5] != amount_cents:
                raise ValueError("recurring_bank_amount_mismatch")
            if payout[6] != currency:
                raise ValueError("recurring_bank_currency_mismatch")
            if received_at < parse_time(
                    payout[7], "recurring_payout_available_at"):
                raise ValueError("recurring_bank_before_withdrawable")
            normalized = {
                "opportunity_id": opportunity_id,
                "recurring_payout_receipt_id":
                    recurring_payout_receipt_id,
                "financial_institution": institution,
                "external_transfer_id": external_id,
                "evidence_url": evidence_url,
                "amount_cents": amount_cents,
                "currency": currency,
                "received_at": received_at.isoformat(),
            }
            serialized = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "recurbank_" + receipt_hash[:24]
            existing = connection.execute(
                """SELECT receipt_id,receipt_hash
                   FROM recurring_bank_receipts
                   WHERE recurring_payout_receipt_id=?
                      OR (financial_institution=? AND external_transfer_id=?)""",
                (recurring_payout_receipt_id, institution,
                 external_id)).fetchone()
            if existing:
                if existing[1] != receipt_hash:
                    raise ValueError("recurring_bank_evidence_conflict")
                return {
                    "receipt_id": existing[0], "changed": False,
                    "status": "recurring_bank_received_verified",
                    "amount_cents": amount_cents}
            connection.execute(
                """INSERT INTO recurring_bank_receipts
                   (receipt_id,opportunity_id,recurring_payout_receipt_id,
                    financial_institution,external_transfer_id,evidence_url,
                    amount_cents,currency,received_at,receipt_hash,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                    receipt_id, opportunity_id,
                    recurring_payout_receipt_id, institution, external_id,
                    evidence_url, amount_cents, currency,
                    received_at.isoformat(), receipt_hash,
                    recorded.isoformat()))
            return {
                "receipt_id": receipt_id, "changed": True,
                "status": "recurring_bank_received_verified",
                "amount_cents": amount_cents}
    finally:
        connection.close()


def record_recurring_realized_unit_economics(
        path, opportunity_id, recurring_payment_receipt_id, economics, *, now=None):
    """Record realized economics from one settled recurring receipt."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if (not isinstance(recurring_payment_receipt_id, str)
            or not recurring_payment_receipt_id.strip()):
        raise ValueError("recurring_payment_receipt_id_required")
    if not isinstance(economics, dict):
        raise ValueError("realized_economics_object_required")
    opportunity_id = opportunity_id.strip()
    recurring_payment_receipt_id = recurring_payment_receipt_id.strip()

    costs = {}
    for field in ("delivery_cost_cents", "inference_cost_cents", "cac_cents"):
        value = finite_number(economics, field, minimum=0)
        if not value.is_integer():
            raise ValueError(f"{field}_invalid")
        costs[field] = int(value)
    minutes = finite_number(
        economics, "human_operating_minutes", minimum=1, maximum=600000)
    if not minutes.is_integer():
        raise ValueError("human_operating_minutes_invalid")
    minutes = int(minutes)
    evidence = {}
    for field in (
            "delivery_cost_evidence_url", "inference_cost_evidence_url",
            "cac_evidence_url", "human_time_evidence_url"):
        url = canonical_url(_proposal_text(economics.get(field), field, 2000))
        if urlsplit(url).scheme != "https":
            raise ValueError(f"{field}_https_required")
        evidence[field] = url
    measured_at = parse_time(economics.get("measured_at"), "measured_at")
    recorded = now or utc_now()
    if measured_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("measured_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            if connection.execute(
                    "SELECT 1 FROM opportunities WHERE id=?",
                    (opportunity_id,)).fetchone() is None:
                raise ValueError("opportunity_not_found")
            payment = _verified_recurring_payment_receipt(
                connection, recurring_payment_receipt_id)
            if payment[0] != opportunity_id:
                raise ValueError("realized_economics_opportunity_mismatch")
            if measured_at < parse_time(payment[16], "payment_settled_at"):
                raise ValueError("economics_measured_before_settlement")
            net_collected = payment[10]
            contribution = net_collected - sum(costs.values())
            hours = minutes / 60
            normalized = {
                "opportunity_id": opportunity_id,
                "recurring_payment_receipt_id": recurring_payment_receipt_id,
                "net_collected_cents": net_collected,
                **costs,
                "human_operating_minutes": minutes,
                "contribution_cents": contribution,
                "contribution_margin": round(
                    contribution / net_collected, 6),
                "revenue_per_human_hour": round(
                    net_collected / 100 / hours, 2),
                "contribution_per_human_hour": round(
                    contribution / 100 / hours, 2),
                "currency": payment[11],
                "evidence": evidence,
                "measured_at": measured_at.isoformat(),
                "evidence_status":
                    "realized_from_settled_recurring_payment",
            }
            serialized = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            evidence_hash = hashlib.sha256(serialized.encode()).hexdigest()
            economics_id = "rruec_" + evidence_hash[:24]
            existing = connection.execute(
                """SELECT economics_id
                   FROM recurring_realized_unit_economics
                   WHERE recurring_payment_receipt_id=?""",
                (recurring_payment_receipt_id,)).fetchone()
            if existing:
                if existing[0] != economics_id:
                    raise ValueError("recurring_realized_economics_conflict")
                return {
                    "economics_id": economics_id, "changed": False,
                    **normalized}
            connection.execute(
                """INSERT INTO recurring_realized_unit_economics
                   (economics_id,opportunity_id,recurring_payment_receipt_id,
                    net_collected_cents,delivery_cost_cents,inference_cost_cents,
                    cac_cents,human_operating_minutes,contribution_cents,
                    contribution_margin,revenue_per_human_hour,
                    contribution_per_human_hour,currency,evidence_json,
                    evidence_hash,measured_at,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (economics_id, opportunity_id, recurring_payment_receipt_id,
                 net_collected, costs["delivery_cost_cents"],
                 costs["inference_cost_cents"], costs["cac_cents"], minutes,
                 contribution, normalized["contribution_margin"],
                 normalized["revenue_per_human_hour"],
                 normalized["contribution_per_human_hour"], payment[11],
                 json.dumps(evidence, sort_keys=True, separators=(",", ":")),
                 evidence_hash, measured_at.isoformat(), recorded.isoformat()))
            return {
                "economics_id": economics_id, "changed": True, **normalized}
    finally:
        connection.close()


def record_growth_evidence(
        path, opportunity_id, payment_receipt_id, kind, evidence, *, now=None):
    """Record retention or expansion evidence linked to a settled payment."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(payment_receipt_id, str) or not payment_receipt_id.strip():
        raise ValueError("payment_receipt_id_required")
    kind = str(kind or "").strip().lower()
    if kind not in {"retention", "expansion"}:
        raise ValueError("growth_evidence_kind_invalid")
    if not isinstance(evidence, dict):
        raise ValueError("growth_evidence_object_required")
    opportunity_id = opportunity_id.strip()
    payment_receipt_id = payment_receipt_id.strip()
    provider = _proposal_text(evidence.get("provider"), "growth_provider", 160)
    external_event_id = _proposal_text(
        evidence.get("external_event_id"), "growth_external_event_id", 500)
    evidence_url = canonical_url(
        _proposal_text(evidence.get("evidence_url"), "growth_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("growth_evidence_url_https_required")
    occurred_at = parse_time(evidence.get("occurred_at"), "growth_occurred_at")
    recorded = now or utc_now()
    if occurred_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("growth_occurred_at_future")

    normalized = {
        "opportunity_id": opportunity_id,
        "payment_receipt_id": payment_receipt_id,
        "kind": kind,
        "provider": provider,
        "external_event_id": external_event_id,
        "evidence_url": evidence_url,
        "occurred_at": occurred_at.isoformat(),
    }
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
    receipt_id = "grow_" + receipt_hash[:24]

    connection = open_ledger(path)
    try:
        with connection:
            if connection.execute(
                    "SELECT 1 FROM opportunities WHERE id=?",
                    (opportunity_id,)).fetchone() is None:
                raise ValueError("opportunity_not_found")
            # Growth claims can promote reusable IP, so derive them only
            # from the same immutable payment snapshot used for revenue.
            payment = _verified_payment_receipt(
                connection, payment_receipt_id)
            if payment[0] != opportunity_id:
                raise ValueError("growth_evidence_opportunity_mismatch")
            if occurred_at < parse_time(payment[10], "payment_settled_at"):
                raise ValueError("growth_evidence_before_settlement")
            existing = connection.execute(
                """SELECT receipt_id,receipt_hash FROM growth_evidence_receipts
                   WHERE provider=? AND kind=? AND external_event_id=?""",
                (provider, kind, external_event_id)).fetchone()
            if existing:
                if existing[1] != receipt_hash:
                    raise ValueError("growth_evidence_conflict")
                return {"receipt_id": existing[0], "changed": False, **normalized}
            connection.execute(
                """INSERT INTO growth_evidence_receipts
                   (receipt_id,opportunity_id,payment_receipt_id,kind,provider,
                    external_event_id,evidence_url,occurred_at,receipt_hash,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (receipt_id, opportunity_id, payment_receipt_id, kind, provider,
                 external_event_id, evidence_url, occurred_at.isoformat(),
                 receipt_hash, recorded.isoformat()))
            return {"receipt_id": receipt_id, "changed": True, **normalized}
    finally:
        connection.close()


def _verified_growth_evidence(connection, receipt_id):
    """Rebuild one-time growth evidence and its settled-payment lineage."""
    row = connection.execute(
        """SELECT opportunity_id,payment_receipt_id,kind,provider,
                  external_event_id,evidence_url,occurred_at,receipt_hash
           FROM growth_evidence_receipts WHERE receipt_id=?""",
        (receipt_id,),
    ).fetchone()
    if row is None:
        raise ValueError("growth_evidence_receipt_not_found")
    normalized = {
        "opportunity_id": row[0],
        "payment_receipt_id": row[1],
        "kind": row[2],
        "provider": row[3],
        "external_event_id": row[4],
        "evidence_url": row[5],
        "occurred_at": row[6],
    }
    serialized = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    if (
        row[2] not in {"retention", "expansion"}
        or row[7] != expected_hash
        or receipt_id != "grow_" + expected_hash[:24]
    ):
        raise ValueError("growth_evidence_unverified")
    try:
        payment = _verified_payment_receipt(connection, row[1])
    except ValueError as exc:
        raise ValueError("growth_evidence_unverified") from exc
    if (
        payment[0] != row[0]
        or parse_time(row[6], "growth_occurred_at")
           < parse_time(payment[10], "payment_settled_at")
    ):
        raise ValueError("growth_evidence_unverified")
    return normalized


def record_recurring_growth_evidence(
        path, opportunity_id, recurring_payment_receipt_id, kind, evidence,
        *, now=None):
    """Record ledger-backed retention or expansion from settled recurring work."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(recurring_payment_receipt_id, str) or not recurring_payment_receipt_id.strip():
        raise ValueError("recurring_payment_receipt_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("recurring_growth_evidence_object_required")
    opportunity_id = opportunity_id.strip()
    recurring_payment_receipt_id = recurring_payment_receipt_id.strip()
    kind = str(kind or "").strip().lower()
    if kind not in {"retention", "expansion"}:
        raise ValueError("growth_evidence_kind_invalid")
    provider = _proposal_text(evidence.get("provider"), "growth_provider", 160)
    external_event_id = _proposal_text(
        evidence.get("external_event_id"), "growth_external_event_id", 500)
    evidence_url = canonical_url(
        _proposal_text(evidence.get("evidence_url"), "growth_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("growth_evidence_url_https_required")
    occurred_at = parse_time(evidence.get("occurred_at"), "growth_occurred_at")
    recorded = now or utc_now()
    if occurred_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("growth_occurred_at_future")

    normalized = {
        "opportunity_id": opportunity_id,
        "recurring_payment_receipt_id": recurring_payment_receipt_id,
        "kind": kind,
        "provider": provider,
        "external_event_id": external_event_id,
        "evidence_url": evidence_url,
        "occurred_at": occurred_at.isoformat(),
    }
    connection = open_ledger(path)
    try:
        with connection:
            payment = _verified_recurring_payment_receipt(
                connection, recurring_payment_receipt_id)
            if payment[0] != opportunity_id:
                raise ValueError("growth_evidence_opportunity_mismatch")
            if occurred_at < parse_time(payment[16], "recurring_settled_at"):
                raise ValueError("growth_evidence_before_settlement")
            economics_row = connection.execute(
                """SELECT economics_id FROM recurring_realized_unit_economics
                   WHERE recurring_payment_receipt_id=?""",
                (recurring_payment_receipt_id,)).fetchone()
            if economics_row is None:
                raise ValueError("positive_recurring_contribution_required")
            economics = _verified_realized_economics(
                connection, economics_row[0], recurring=True)
            if economics["contribution_cents"] <= 0:
                raise ValueError("positive_recurring_contribution_required")
            normalized["recurring_economics_id"] = economics_row[0]

            prior_id = None
            baseline_scope = None
            expanded_scope = None
            baseline_value = None
            expanded_value = None
            if kind == "retention":
                prior_id = _proposal_text(
                    evidence.get("prior_recurring_payment_receipt_id"),
                    "prior_recurring_payment_receipt_id", 160)
                if prior_id == recurring_payment_receipt_id:
                    raise ValueError("retention_prior_receipt_invalid")
                try:
                    prior = _verified_recurring_payment_receipt(
                        connection, prior_id)
                except ValueError as exc:
                    if str(exc) == "recurring_payment_receipt_not_found":
                        raise ValueError(
                            "prior_recurring_payment_receipt_not_found") from exc
                    raise
                if prior[0] != opportunity_id:
                    raise ValueError("growth_evidence_opportunity_mismatch")
                if parse_time(payment[12], "service_period_start") < parse_time(
                        prior[13], "prior_service_period_end"):
                    raise ValueError("retention_subsequent_service_period_required")
                normalized["prior_recurring_payment_receipt_id"] = prior_id
            else:
                baseline_scope = _proposal_text(
                    evidence.get("baseline_scope"), "baseline_scope", 1000)
                expanded_scope = _proposal_text(
                    evidence.get("expanded_scope"), "expanded_scope", 1000)
                if baseline_scope == expanded_scope:
                    raise ValueError("expansion_scope_growth_required")
                baseline_number = finite_number(
                    evidence, "baseline_value_cents", minimum=0)
                expanded_number = finite_number(
                    evidence, "expanded_value_cents", minimum=1)
                if not baseline_number.is_integer() or not expanded_number.is_integer():
                    raise ValueError("expansion_value_cents_invalid")
                baseline_value = int(baseline_number)
                expanded_value = int(expanded_number)
                if expanded_value <= baseline_value:
                    raise ValueError("expansion_value_growth_required")
                normalized.update({
                    "baseline_scope": baseline_scope,
                    "expanded_scope": expanded_scope,
                    "baseline_value_cents": baseline_value,
                    "expanded_value_cents": expanded_value,
                })

            serialized = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            receipt_id = "rgrow_" + receipt_hash[:24]
            existing = connection.execute(
                """SELECT receipt_id,receipt_hash
                   FROM recurring_growth_evidence_receipts
                   WHERE provider=? AND kind=? AND external_event_id=?""",
                (provider, kind, external_event_id)).fetchone()
            if existing:
                if existing[1] != receipt_hash:
                    raise ValueError("growth_evidence_conflict")
                return {"receipt_id": existing[0], "changed": False, **normalized}
            connection.execute(
                """INSERT INTO recurring_growth_evidence_receipts
                   (receipt_id,opportunity_id,recurring_payment_receipt_id,
                    recurring_economics_id,kind,provider,external_event_id,
                    evidence_url,prior_recurring_payment_receipt_id,
                    baseline_scope,expanded_scope,baseline_value_cents,
                    expanded_value_cents,occurred_at,receipt_hash,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (receipt_id, opportunity_id, recurring_payment_receipt_id,
                 economics_row[0], kind, provider, external_event_id,
                 evidence_url,
                 prior_id, baseline_scope, expanded_scope, baseline_value,
                 expanded_value, occurred_at.isoformat(), receipt_hash,
                 recorded.isoformat()))
            return {"receipt_id": receipt_id, "changed": True, **normalized}
    finally:
        connection.close()


def record_reusable_ip_reuse_evidence(
        path, source_asset_id, reused_asset_id, economics_id, evidence,
        *, economics_kind="one_time", now=None):
    """Record independently settled positive-margin reuse by another opportunity."""
    source_asset_id = _proposal_text(
        source_asset_id, "source_asset_id", 160)
    reused_asset_id = _proposal_text(
        reused_asset_id, "reused_asset_id", 160)
    economics_id = _proposal_text(economics_id, "economics_id", 160)
    economics_kind = str(economics_kind or "").strip().lower()
    if economics_kind not in {"one_time", "recurring"}:
        raise ValueError("reuse_economics_kind_invalid")
    if not isinstance(evidence, dict):
        raise ValueError("reuse_evidence_object_required")
    provider = _proposal_text(evidence.get("provider"), "reuse_provider", 160)
    external_event_id = _proposal_text(
        evidence.get("external_event_id"), "reuse_external_event_id", 500)
    evidence_url = canonical_url(
        _proposal_text(evidence.get("evidence_url"), "reuse_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("reuse_evidence_url_https_required")
    occurred_at = parse_time(evidence.get("occurred_at"), "reuse_occurred_at")
    recorded = now or utc_now()
    if occurred_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("reuse_occurred_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            source = connection.execute(
                """SELECT opportunity_id,name,asset_type
                   FROM reusable_ip_assets WHERE asset_id=?""",
                (source_asset_id,)).fetchone()
            reused = connection.execute(
                """SELECT opportunity_id,name,asset_type
                   FROM reusable_ip_assets WHERE asset_id=?""",
                (reused_asset_id,)).fetchone()
            if source is None or reused is None:
                raise ValueError("reusable_ip_asset_not_found")
            if source[0] == reused[0]:
                raise ValueError("cross_opportunity_reuse_required")
            if source[1].casefold() != reused[1].casefold() or source[2] != reused[2]:
                raise ValueError("reused_asset_identity_mismatch")
            if economics_kind == "recurring":
                economics = _verified_realized_economics(
                    connection, economics_id, recurring=True)
            else:
                economics = _verified_realized_economics(
                    connection, economics_id)
            if economics["opportunity_id"] != reused[0]:
                raise ValueError("reuse_economics_opportunity_mismatch")
            if economics["contribution_cents"] <= 0:
                raise ValueError("positive_contribution_required")
            if occurred_at < parse_time(
                    economics["measured_at"], "reuse_economics_measured_at"):
                raise ValueError("reuse_evidence_before_economics")
            normalized = {
                "source_asset_id": source_asset_id,
                "source_opportunity_id": source[0],
                "reused_asset_id": reused_asset_id,
                "reused_opportunity_id": reused[0],
                "economics_kind": economics_kind,
                "economics_id": economics_id,
                "settled_payment_receipt_id": economics["payment_receipt_id"],
                "provider": provider,
                "external_event_id": external_event_id,
                "evidence_url": evidence_url,
                "occurred_at": occurred_at.isoformat(),
            }
            receipt_json = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(receipt_json.encode()).hexdigest()
            receipt_id = "ipr_" + receipt_hash[:24]
            existing = connection.execute(
                """SELECT receipt_id,receipt_hash
                   FROM reusable_ip_reuse_receipts
                   WHERE provider=? AND external_event_id=?""",
                (provider, external_event_id)).fetchone()
            if existing:
                if existing[1] != receipt_hash:
                    raise ValueError("reuse_evidence_conflict")
                return {"receipt_id": existing[0], "changed": False, **normalized}
            connection.execute(
                """INSERT INTO reusable_ip_reuse_receipts
                   (receipt_id,source_asset_id,source_opportunity_id,
                    reused_asset_id,reused_opportunity_id,economics_kind,
                    economics_id,provider,external_event_id,evidence_url,
                    occurred_at,receipt_hash,recorded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (receipt_id, source_asset_id, source[0], reused_asset_id,
                 reused[0], economics_kind, economics_id, provider,
                 external_event_id, evidence_url, occurred_at.isoformat(),
                 receipt_hash, recorded.isoformat()))
            return {"receipt_id": receipt_id, "changed": True, **normalized}
    finally:
        connection.close()


def _verified_reusable_ip_reuse_evidence(connection, receipt_id):
    """Rebuild a reuse receipt and reverify its settled economics lineage."""
    row = connection.execute(
        """SELECT source_asset_id,source_opportunity_id,reused_asset_id,
                  reused_opportunity_id,economics_kind,economics_id,provider,
                  external_event_id,evidence_url,occurred_at,receipt_hash
           FROM reusable_ip_reuse_receipts WHERE receipt_id=?""",
        (receipt_id,),
    ).fetchone()
    if row is None:
        raise ValueError("reusable_ip_reuse_receipt_not_found")
    if row[4] not in {"one_time", "recurring"}:
        raise ValueError("reusable_ip_reuse_evidence_unverified")
    source = connection.execute(
        """SELECT opportunity_id,name,asset_type
           FROM reusable_ip_assets WHERE asset_id=?""",
        (row[0],),
    ).fetchone()
    reused = connection.execute(
        """SELECT opportunity_id,name,asset_type
           FROM reusable_ip_assets WHERE asset_id=?""",
        (row[2],),
    ).fetchone()
    try:
        economics = _verified_realized_economics(
            connection, row[5], recurring=row[4] == "recurring")
    except ValueError as exc:
        raise ValueError("reusable_ip_reuse_evidence_unverified") from exc
    if (
        source is None
        or reused is None
        or source[0] != row[1]
        or reused[0] != row[3]
        or row[1] == row[3]
        or source[1].casefold() != reused[1].casefold()
        or source[2] != reused[2]
        or economics["opportunity_id"] != row[3]
        or economics["contribution_cents"] <= 0
        or parse_time(row[9], "reuse_occurred_at")
           < parse_time(economics["measured_at"], "reuse_economics_measured_at")
    ):
        raise ValueError("reusable_ip_reuse_evidence_unverified")
    normalized = {
        "source_asset_id": row[0],
        "source_opportunity_id": row[1],
        "reused_asset_id": row[2],
        "reused_opportunity_id": row[3],
        "economics_kind": row[4],
        "economics_id": row[5],
        "settled_payment_receipt_id": economics["payment_receipt_id"],
        "provider": row[6],
        "external_event_id": row[7],
        "evidence_url": row[8],
        "occurred_at": row[9],
    }
    serialized = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    if row[10] != expected_hash or receipt_id != "ipr_" + expected_hash[:24]:
        raise ValueError("reusable_ip_reuse_evidence_unverified")
    return normalized


def _verified_reusable_ip_maturity(connection, asset_id):
    """Rebuild an asset's earned-mastery chain from immutable ledger receipts."""
    asset = connection.execute(
        """SELECT opportunity_id,maturity,evidence_json,evidence_hash
           FROM reusable_ip_assets WHERE asset_id=?""", (asset_id,)).fetchone()
    if asset is None:
        raise ValueError("reusable_ip_maturity_unverified")
    opportunity_id, claimed_maturity, asset_evidence, asset_hash = asset
    if claimed_maturity not in REUSABLE_IP_MATURITY:
        raise ValueError("reusable_ip_maturity_unverified")
    promotions = connection.execute(
        """SELECT promotion_id,from_maturity,to_maturity,evidence_json,
                  evidence_hash
           FROM reusable_ip_promotions WHERE asset_id=?
           ORDER BY rowid""", (asset_id,)).fetchall()
    expected_count = REUSABLE_IP_MATURITY[claimed_maturity]
    if len(promotions) != expected_count:
        raise ValueError("reusable_ip_maturity_unverified")

    current = "learned"
    last_json = last_hash = None
    for promotion in promotions:
        promotion_id, from_maturity, to_maturity, evidence_json, evidence_hash = promotion
        if (
            from_maturity != current
            or REUSABLE_IP_MATURITY.get(to_maturity) != REUSABLE_IP_MATURITY[current] + 1
        ):
            raise ValueError("reusable_ip_maturity_unverified")
        try:
            evidence = json.loads(evidence_json)
        except (TypeError, ValueError) as exc:
            raise ValueError("reusable_ip_maturity_unverified") from exc
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
        if (
            canonical != evidence_json
            or evidence_hash != expected_hash
            or promotion_id != "ipp_" + expected_hash[:24]
            or evidence.get("asset_id") != asset_id
            or evidence.get("opportunity_id") != opportunity_id
            or evidence.get("from_maturity") != from_maturity
            or evidence.get("to_maturity") != to_maturity
        ):
            raise ValueError("reusable_ip_maturity_unverified")

        try:
            if to_maturity == "paid_validated":
                if evidence.get("payment_receipt_id"):
                    receipt = _verified_payment_receipt(
                        connection, evidence["payment_receipt_id"])
                else:
                    receipt = _verified_recurring_payment_receipt(
                        connection, evidence["recurring_payment_receipt_id"])
                if receipt[0] != opportunity_id:
                    raise ValueError("promotion_evidence_opportunity_mismatch")
            elif to_maturity == "repeatable_positive_margin":
                entries = evidence.get("one_time_economics_receipts")
                recurring = False
                if entries is None:
                    entries = evidence.get("recurring_economics_receipts")
                    recurring = True
                if not isinstance(entries, list) or len(entries) < 2:
                    raise ValueError("repeatability_receipts_missing")
                for entry in entries:
                    verified = _verified_realized_economics(
                        connection, entry["economics_id"], recurring=recurring)
                    expected_payment = entry[
                        "recurring_payment_receipt_id" if recurring
                        else "payment_receipt_id"]
                    if verified["payment_receipt_id"] != expected_payment:
                        raise ValueError("repeatability_receipt_mismatch")
            else:
                growth_id = (evidence.get("growth_receipt_id")
                             or evidence.get("recurring_growth_receipt_id"))
                if evidence.get("recurring_growth_receipt_id"):
                    growth = _verified_recurring_growth_evidence(
                        connection, growth_id)
                else:
                    growth = _verified_growth_evidence(connection, growth_id)
                if growth["opportunity_id"] != opportunity_id:
                    raise ValueError("promotion_evidence_opportunity_mismatch")
                expected_kind = (
                    "retention" if to_maturity == "scale_candidate"
                    else "expansion")
                if growth["kind"] != expected_kind:
                    raise ValueError("promotion_growth_kind_mismatch")
                if to_maturity == "productize_candidate":
                    reuse = _verified_reusable_ip_reuse_evidence(
                        connection, evidence["reuse_receipt_id"])
                    if (
                        reuse["source_asset_id"] != asset_id
                        or reuse["source_opportunity_id"] != opportunity_id
                    ):
                        raise ValueError("promotion_reuse_source_mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("reusable_ip_maturity_unverified") from exc
        current = to_maturity
        last_json, last_hash = evidence_json, evidence_hash

    if current != claimed_maturity:
        raise ValueError("reusable_ip_maturity_unverified")
    if promotions and (asset_evidence != last_json or asset_hash != last_hash):
        raise ValueError("reusable_ip_maturity_unverified")
    return {
        "asset_id": asset_id,
        "opportunity_id": opportunity_id,
        "maturity": claimed_maturity,
        "promotion_count": len(promotions),
    }


def promote_reusable_ip_asset(
        path, opportunity_id, asset_id, target_maturity, evidence, *, now=None):
    """Promote reusable IP only through evidence resolved from the ledger."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise ValueError("asset_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("promotion_evidence_object_required")
    opportunity_id = opportunity_id.strip()
    asset_id = asset_id.strip()
    target_maturity = str(target_maturity or "").strip().lower()
    if target_maturity not in REUSABLE_IP_MATURITY or target_maturity == "learned":
        raise ValueError("promotion_target_invalid")
    recorded = now or utc_now()

    connection = open_ledger(path)
    try:
        with connection:
            asset = connection.execute(
                """SELECT opportunity_id,maturity,name,asset_type
                   FROM reusable_ip_assets WHERE asset_id=?""",
                (asset_id,)).fetchone()
            if asset is None:
                raise ValueError("reusable_ip_asset_not_found")
            if asset[0] != opportunity_id:
                raise ValueError("reusable_ip_asset_opportunity_mismatch")
            current = asset[1]
            existing = connection.execute(
                """SELECT promotion_id,evidence_json FROM reusable_ip_promotions
                   WHERE asset_id=? AND to_maturity=?""",
                (asset_id, target_maturity)).fetchone()
            if current == target_maturity and existing:
                return {
                    "promotion_id": existing[0], "changed": False,
                    "asset_id": asset_id, "maturity": target_maturity,
                    "evidence": json.loads(existing[1]),
                }
            if REUSABLE_IP_MATURITY[target_maturity] != (
                    REUSABLE_IP_MATURITY.get(current, -100) + 1):
                raise ValueError("reusable_ip_promotion_sequence_invalid")

            resolved = {}
            if target_maturity == "paid_validated":
                payment_reference = evidence.get("payment_receipt_id")
                recurring_reference = evidence.get(
                    "recurring_payment_receipt_id")
                if bool(payment_reference) == bool(recurring_reference):
                    raise ValueError("exactly_one_payment_receipt_required")
                if recurring_reference:
                    reference = _proposal_text(
                        recurring_reference,
                        "recurring_payment_receipt_id", 160)
                    row = connection.execute(
                        """SELECT opportunity_id
                           FROM recurring_payment_receipts
                           WHERE receipt_id=?""", (reference,)).fetchone()
                    missing_error = "recurring_payment_receipt_not_found"
                    resolved_key = "recurring_payment_receipt_id"
                else:
                    reference = _proposal_text(
                        payment_reference, "payment_receipt_id", 160)
                    row = connection.execute(
                        """SELECT opportunity_id FROM payment_receipts
                           WHERE receipt_id=?""", (reference,)).fetchone()
                    missing_error = "payment_receipt_not_found"
                    resolved_key = "payment_receipt_id"
                if row is None:
                    raise ValueError(missing_error)
                if row[0] != opportunity_id:
                    raise ValueError("promotion_evidence_opportunity_mismatch")
                resolved = {resolved_key: reference}
            elif target_maturity == "repeatable_positive_margin":
                if evidence.get("economics_id"):
                    raise ValueError(
                        "one_time_repeatability_requires_multiple_receipts")
                if evidence.get("recurring_economics_id"):
                    raise ValueError(
                        "recurring_repeatability_requires_multiple_receipts")
                one_time_references = evidence.get("economics_ids")
                recurring_references = evidence.get(
                    "recurring_economics_ids")
                if bool(one_time_references) == bool(recurring_references):
                    raise ValueError(
                        "exactly_one_realized_economics_path_required")
                if recurring_references:
                    if (not isinstance(recurring_references, list)
                            or len(recurring_references) < 2
                            or len(recurring_references) > 24):
                        raise ValueError(
                            "recurring_repeatability_requires_multiple_receipts")
                    normalized_references = []
                    seen_economics = set()
                    seen_payments = set()
                    for raw_reference in recurring_references:
                        reference = _proposal_text(
                            raw_reference, "recurring_economics_id", 160)
                        if reference in seen_economics:
                            raise ValueError(
                                "recurring_economics_receipts_must_be_distinct")
                        row = _verified_realized_economics(
                            connection, reference, recurring=True)
                        if row["opportunity_id"] != opportunity_id:
                            raise ValueError(
                                "promotion_evidence_opportunity_mismatch")
                        if row["contribution_cents"] <= 0:
                            raise ValueError("positive_contribution_required")
                        if row["payment_receipt_id"] in seen_payments:
                            raise ValueError(
                                "recurring_payment_receipts_must_be_distinct")
                        seen_economics.add(reference)
                        seen_payments.add(row["payment_receipt_id"])
                        normalized_references.append({
                            "economics_id": reference,
                            "recurring_payment_receipt_id":
                                row["payment_receipt_id"],
                        })
                    resolved = {
                        "recurring_economics_receipts":
                            normalized_references,
                        "repeatability_receipt_count":
                            len(normalized_references),
                    }
                else:
                    if (not isinstance(one_time_references, list)
                            or len(one_time_references) < 2
                            or len(one_time_references) > 24):
                        raise ValueError(
                            "one_time_repeatability_requires_multiple_receipts")
                    normalized_references = []
                    seen_economics = set()
                    seen_payments = set()
                    seen_opportunities = set()
                    for raw_reference in one_time_references:
                        reference = _proposal_text(
                            raw_reference, "economics_id", 160)
                        if reference in seen_economics:
                            raise ValueError(
                                "one_time_economics_receipts_must_be_distinct")
                        row = _verified_realized_economics(
                            connection, reference)
                        if row["contribution_cents"] <= 0:
                            raise ValueError("positive_contribution_required")
                        if row["payment_receipt_id"] in seen_payments:
                            raise ValueError(
                                "one_time_payment_receipts_must_be_distinct")
                        if row["opportunity_id"] != opportunity_id:
                            linked_asset = connection.execute(
                                """SELECT 1 FROM reusable_ip_assets
                                   WHERE opportunity_id=?
                                     AND lower(name)=lower(?)
                                     AND asset_type=?""",
                                (row["opportunity_id"], asset[2],
                                 asset[3])).fetchone()
                            if linked_asset is None:
                                raise ValueError(
                                    "repeatability_asset_identity_mismatch")
                        seen_economics.add(reference)
                        seen_payments.add(row["payment_receipt_id"])
                        seen_opportunities.add(row["opportunity_id"])
                        normalized_references.append({
                            "economics_id": reference,
                            "payment_receipt_id": row["payment_receipt_id"],
                            "opportunity_id": row["opportunity_id"],
                        })
                    if opportunity_id not in seen_opportunities:
                        raise ValueError(
                            "source_opportunity_economics_required")
                    resolved = {
                        "one_time_economics_receipts":
                            normalized_references,
                        "repeatability_receipt_count":
                            len(normalized_references),
                    }
            else:
                expected_kind = (
                    "retention" if target_maturity == "scale_candidate"
                    else "expansion")
                growth_reference = evidence.get("growth_receipt_id")
                recurring_reference = evidence.get(
                    "recurring_growth_receipt_id")
                if bool(growth_reference) == bool(recurring_reference):
                    raise ValueError("exactly_one_growth_receipt_required")
                if recurring_reference:
                    reference = _proposal_text(
                        recurring_reference,
                        "recurring_growth_receipt_id", 160)
                    try:
                        row = _verified_recurring_growth_evidence(
                            connection, reference)
                    except ValueError as exc:
                        raise ValueError(
                            "growth_evidence_receipt_unverified") from exc
                    resolved_key = "recurring_growth_receipt_id"
                else:
                    reference = _proposal_text(
                        growth_reference, "growth_receipt_id", 160)
                    try:
                        row = _verified_growth_evidence(
                            connection, reference)
                    except ValueError as exc:
                        raise ValueError(
                            "growth_evidence_receipt_unverified") from exc
                    resolved_key = "growth_receipt_id"
                if row["opportunity_id"] != opportunity_id:
                    raise ValueError("promotion_evidence_opportunity_mismatch")
                if row["kind"] != expected_kind:
                    raise ValueError(f"{expected_kind}_evidence_required")
                resolved = {
                    resolved_key: reference,
                    "growth_kind": expected_kind,
                }
                if target_maturity == "productize_candidate":
                    reuse_reference = _proposal_text(
                        evidence.get("reuse_receipt_id"),
                        "reuse_receipt_id", 160)
                    try:
                        reuse = _verified_reusable_ip_reuse_evidence(
                            connection, reuse_reference)
                    except ValueError as exc:
                        raise ValueError(
                            "reuse_evidence_receipt_unverified") from exc
                    if (
                        reuse["source_asset_id"] != asset_id
                        or reuse["source_opportunity_id"] != opportunity_id
                    ):
                        raise ValueError(
                            "promotion_reuse_evidence_source_mismatch")
                    if reuse["reused_opportunity_id"] == opportunity_id:
                        raise ValueError("cross_opportunity_reuse_required")
                    resolved.update({
                        "reuse_receipt_id": reuse_reference,
                        "reused_opportunity_id":
                            reuse["reused_opportunity_id"],
                        "reuse_economics_kind": reuse["economics_kind"],
                        "reuse_economics_id": reuse["economics_id"],
                    })

            normalized = {
                "asset_id": asset_id,
                "opportunity_id": opportunity_id,
                "from_maturity": current,
                "to_maturity": target_maturity,
                **resolved,
            }
            evidence_json = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"))
            evidence_hash = hashlib.sha256(evidence_json.encode()).hexdigest()
            promotion_id = "ipp_" + evidence_hash[:24]
            connection.execute(
                """INSERT INTO reusable_ip_promotions
                   (promotion_id,asset_id,opportunity_id,from_maturity,to_maturity,
                    evidence_json,evidence_hash,promoted_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (promotion_id, asset_id, opportunity_id, current, target_maturity,
                 evidence_json, evidence_hash, recorded.isoformat()))
            connection.execute(
                """UPDATE reusable_ip_assets
                   SET maturity=?,evidence_json=?,evidence_hash=?,updated_at=?
                   WHERE asset_id=?""",
                (target_maturity, evidence_json, evidence_hash,
                 recorded.isoformat(), asset_id))
            return {
                "promotion_id": promotion_id, "changed": True,
                "asset_id": asset_id, "maturity": target_maturity,
                "evidence": normalized,
            }
    finally:
        connection.close()


def record_withdrawable_balance(path, opportunity_id, payment_receipt_id, evidence, *, now=None):
    """Record provider evidence that a collected payment is available to withdraw."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(payment_receipt_id, str) or not payment_receipt_id.strip():
        raise ValueError("payment_receipt_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("withdrawable_evidence_object_required")
    opportunity_id = opportunity_id.strip()
    payment_receipt_id = payment_receipt_id.strip()
    provider = _proposal_text(evidence.get("provider"), "payout_provider", 160)
    external_id = _proposal_text(
        evidence.get("external_balance_id"), "external_balance_id", 500)
    evidence_url = canonical_url(
        _proposal_text(evidence.get("evidence_url"), "payout_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("payout_evidence_url_https_required")
    amount = finite_number(evidence, "amount_cents", minimum=1)
    if not amount.is_integer():
        raise ValueError("amount_cents_invalid")
    amount_cents = int(amount)
    currency = _proposal_text(evidence.get("currency"), "payout_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("payout_currency_invalid")
    available_at = parse_time(evidence.get("available_at"), "available_at")
    recorded = now or utc_now()
    if available_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("available_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            payment = _verified_payment_receipt(
                connection, payment_receipt_id)
            if payment[0] != opportunity_id:
                raise ValueError("payout_opportunity_mismatch")
            if payment[2].casefold() != provider.casefold():
                raise ValueError("payout_provider_mismatch")
            if payment[7] != amount_cents:
                raise ValueError("payout_amount_mismatch")
            if payment[8] != currency:
                raise ValueError("payout_currency_mismatch")
            if available_at < parse_time(payment[10], "payment_settled_at"):
                raise ValueError("withdrawable_before_settlement")
            receipt = {"opportunity_id": opportunity_id,
                       "payment_receipt_id": payment_receipt_id,
                       "provider": provider, "external_balance_id": external_id,
                       "evidence_url": evidence_url, "amount_cents": amount_cents,
                       "currency": currency, "available_at": available_at.isoformat()}
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            rid = "pavr_" + receipt_hash[:24]
            evidence_id = "withdrawable_balance:" + rid
            existing = connection.execute(
                "SELECT 1 FROM payout_availability_receipts WHERE receipt_id=?", (rid,)
            ).fetchone()
            if row[0] in {"withdrawable", "received"} and existing:
                return {"receipt_id": rid, "changed": False, "state": row[0],
                        "amount_cents": amount_cents}
            if row[0] != "collected":
                raise ValueError("pipeline_state_conflict")
            recorded_at = recorded.isoformat()
            tid = transition_id(opportunity_id, "collected", "withdrawable", evidence_id)
            connection.execute("""INSERT INTO payout_availability_receipts
                (receipt_id,opportunity_id,payment_receipt_id,provider,external_balance_id,
                 evidence_url,amount_cents,currency,available_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                    rid, opportunity_id, payment_receipt_id, provider, external_id,
                    evidence_url, amount_cents, currency, available_at.isoformat(),
                    receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "withdrawable"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("withdrawable", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "collected", "withdrawable", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": rid, "changed": True, "state": "withdrawable",
                "amount_cents": amount_cents}
    finally:
        connection.close()


def _verified_payout_receipt(connection, payout_receipt_id):
    """Return withdrawable evidence only when its immutable snapshot matches."""
    payout = connection.execute(
        """SELECT opportunity_id,payment_receipt_id,provider,
                  external_balance_id,evidence_url,amount_cents,currency,
                  available_at,receipt_hash
           FROM payout_availability_receipts WHERE receipt_id=?""",
        (payout_receipt_id,)).fetchone()
    if payout is None:
        raise ValueError("payout_receipt_not_found")
    snapshot = {
        "opportunity_id": payout[0],
        "payment_receipt_id": payout[1],
        "provider": payout[2],
        "external_balance_id": payout[3],
        "evidence_url": payout[4],
        "amount_cents": payout[5],
        "currency": payout[6],
        "available_at": payout[7],
    }
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode()).hexdigest()
    if payout[8] != expected_hash or payout_receipt_id != (
            "pavr_" + expected_hash[:24]):
        raise ValueError("payout_receipt_unverified")
    return payout


def record_bank_receipt(path, opportunity_id, payout_receipt_id, evidence, *, now=None):
    """Record proof that one withdrawable payout reached the owner's bank account."""
    if not isinstance(opportunity_id, str) or not opportunity_id.strip():
        raise ValueError("opportunity_id_required")
    if not isinstance(payout_receipt_id, str) or not payout_receipt_id.strip():
        raise ValueError("payout_receipt_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("bank_receipt_object_required")
    opportunity_id = opportunity_id.strip()
    payout_receipt_id = payout_receipt_id.strip()
    institution = _proposal_text(
        evidence.get("financial_institution"), "financial_institution", 160)
    external_id = _proposal_text(
        evidence.get("external_transfer_id"), "external_transfer_id", 500)
    evidence_url = canonical_url(
        _proposal_text(evidence.get("evidence_url"), "bank_evidence_url", 2000))
    if urlsplit(evidence_url).scheme != "https":
        raise ValueError("bank_evidence_url_https_required")
    amount = finite_number(evidence, "amount_cents", minimum=1)
    if not amount.is_integer():
        raise ValueError("amount_cents_invalid")
    amount_cents = int(amount)
    currency = _proposal_text(evidence.get("currency"), "bank_currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("bank_currency_invalid")
    received_at = parse_time(evidence.get("received_at"), "received_at")
    recorded = now or utc_now()
    if received_at > recorded + MAX_FUTURE_SKEW:
        raise ValueError("received_at_future")

    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state,payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            payout = _verified_payout_receipt(
                connection, payout_receipt_id)
            if payout[0] != opportunity_id:
                raise ValueError("bank_receipt_opportunity_mismatch")
            if payout[5] != amount_cents:
                raise ValueError("bank_receipt_amount_mismatch")
            if payout[6] != currency:
                raise ValueError("bank_receipt_currency_mismatch")
            if received_at < parse_time(payout[7], "payout_available_at"):
                raise ValueError("bank_receipt_before_withdrawable")
            receipt = {"opportunity_id": opportunity_id,
                       "payout_availability_receipt_id": payout_receipt_id,
                       "financial_institution": institution,
                       "external_transfer_id": external_id,
                       "evidence_url": evidence_url, "amount_cents": amount_cents,
                       "currency": currency, "received_at": received_at.isoformat()}
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            receipt_hash = hashlib.sha256(serialized.encode()).hexdigest()
            rid = "bankr_" + receipt_hash[:24]
            evidence_id = "bank_receipt:" + rid
            existing = connection.execute(
                "SELECT 1 FROM bank_receipts WHERE receipt_id=?", (rid,)).fetchone()
            if row[0] == "received" and existing:
                return {"receipt_id": rid, "changed": False, "state": row[0],
                        "amount_cents": amount_cents}
            if row[0] != "withdrawable":
                raise ValueError("pipeline_state_conflict")
            recorded_at = recorded.isoformat()
            tid = transition_id(opportunity_id, "withdrawable", "received", evidence_id)
            connection.execute("""INSERT INTO bank_receipts
                (receipt_id,opportunity_id,payout_availability_receipt_id,
                 financial_institution,external_transfer_id,evidence_url,amount_cents,
                 currency,received_at,receipt_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                    rid, opportunity_id, payout_receipt_id, institution, external_id,
                    evidence_url, amount_cents, currency, received_at.isoformat(),
                    receipt_hash, recorded_at))
            payload = json.loads(row[1])
            payload["pipeline_state"] = "received"
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?,payload_json=?,updated_at=? WHERE id=?",
                ("received", json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, "withdrawable", "received", evidence_id,
                    hashlib.sha256(evidence_id.encode()).hexdigest(), recorded_at))
        return {"receipt_id": rid, "changed": True, "state": "received",
                "amount_cents": amount_cents}
    finally:
        connection.close()


def record_transition(path, opportunity_id, expected_state, to_state, evidence_id, *, now=None):
    """Record one evidence-backed, no-skip pipeline transition atomically.

    This changes ledger state only. It never submits, contacts, contracts, delivers,
    invoices, or charges through an external provider.
    """
    values = (opportunity_id, expected_state, to_state, evidence_id)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("transition_fields_required")
    opportunity_id, expected_state, to_state, evidence_id = (value.strip() for value in values)
    if to_state not in PIPELINE_TRANSITIONS.get(expected_state, set()):
        raise ValueError("transition_not_allowed")
    if to_state == "proposal_ready":
        raise ValueError("proposal_artifact_required")
    if to_state == "submitted":
        raise ValueError("submission_receipt_required")
    if to_state == "response_received":
        raise ValueError("response_receipt_required")
    if to_state == "contracted":
        raise ValueError("contract_receipt_required")
    if to_state == "executing":
        raise ValueError("execution_plan_required")
    if to_state == "qa_passed":
        raise ValueError("qa_report_required")
    if to_state == "delivered":
        raise ValueError("delivery_receipt_required")
    if to_state == "invoiced":
        raise ValueError("invoice_receipt_required")
    if to_state == "collected":
        raise ValueError("payment_receipt_required")
    if to_state == "withdrawable":
        raise ValueError("withdrawable_balance_receipt_required")
    if to_state == "received":
        raise ValueError("bank_receipt_required")
    if not evidence_id.startswith(PIPELINE_EVIDENCE_PREFIXES[to_state]):
        raise ValueError("transition_evidence_invalid")
    recorded_at = (now or utc_now()).isoformat()
    evidence_hash = hashlib.sha256(evidence_id.encode()).hexdigest()
    tid = transition_id(opportunity_id, expected_state, to_state, evidence_id)
    connection = open_ledger(path)
    try:
        with connection:
            row = connection.execute(
                "SELECT pipeline_state, payload_json FROM opportunities WHERE id=?",
                (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError("opportunity_not_found")
            if row[0] == to_state:
                existing = connection.execute(
                    "SELECT 1 FROM opportunity_transitions WHERE transition_id=?", (tid,)).fetchone()
                if existing:
                    return {"transition_id": tid, "changed": False, "state": to_state}
            if row[0] != expected_state:
                raise ValueError("pipeline_state_conflict")
            payload = json.loads(row[1])
            payload["pipeline_state"] = to_state
            connection.execute(
                "UPDATE opportunities SET pipeline_state=?, payload_json=?, updated_at=? WHERE id=?",
                (to_state, json.dumps(payload, sort_keys=True, separators=(",", ":")),
                 recorded_at, opportunity_id))
            connection.execute("""INSERT INTO opportunity_transitions
                (transition_id,opportunity_id,from_state,to_state,evidence_id,evidence_hash,recorded_at)
                VALUES (?,?,?,?,?,?,?)""", (
                    tid, opportunity_id, expected_state, to_state, evidence_id,
                    evidence_hash, recorded_at))
        return {"transition_id": tid, "changed": True, "state": to_state}
    finally:
        connection.close()


def persist(result, path=DEFAULT_DB_PATH, *, now=None):
    """Atomically persist eligible opportunities and idempotent decision receipts."""
    now = (now or utc_now()).isoformat()
    connection = open_ledger(path)
    written, unchanged, receipt_writes = 0, 0, 0
    offer_evidence_writes, reusable_ip_writes = 0, 0
    try:
        with connection:
            for index, item in enumerate(result["opportunities"]):
                if any(
                        asset.get("maturity", "learned") != "learned"
                        for asset in item.get("reusable_ip_assets", [])):
                    raise ValueError("reusable_ip_promotion_requires_ledger")
                serialized = json.dumps(item, sort_keys=True, separators=(",", ":"))
                cursor = connection.execute("""INSERT INTO opportunities
                    (id,source,external_id,url,title,score,action_mode,pipeline_state,
                     observed_at,payload_json,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                      source=excluded.source, external_id=excluded.external_id,
                      url=excluded.url, title=excluded.title, score=excluded.score,
                      action_mode=excluded.action_mode,
                      pipeline_state=opportunities.pipeline_state,
                      observed_at=excluded.observed_at,
                      payload_json=json_set(excluded.payload_json, '$.pipeline_state',
                                            opportunities.pipeline_state),
                      updated_at=excluded.updated_at
                    WHERE excluded.observed_at > opportunities.observed_at""", (
                        item["id"], item["source"], item["external_id"], item["url"],
                        item["title"], item["score"], item["action_mode"], item["pipeline_state"],
                        item["observed_at"], serialized, now))
                if cursor.rowcount:
                    written += 1
                    for phase, references in item.get("offer_evidence", {}).items():
                        for reference in references:
                            evidence_hash = hashlib.sha256(reference.encode()).hexdigest()
                            evidence_id = "offev_" + hashlib.sha256(
                                f"{item['id']}|{phase}|{reference}".encode()
                            ).hexdigest()[:24]
                            offer_evidence_writes += connection.execute(
                                """INSERT OR IGNORE INTO offer_phase_evidence
                                   (evidence_id,opportunity_id,phase,reference,
                                    evidence_hash,recorded_at)
                                   VALUES (?,?,?,?,?,?)""",
                                (evidence_id, item["id"], phase, reference,
                                 evidence_hash, now),
                            ).rowcount
                    for asset in item.get("reusable_ip_assets", []):
                        evidence_json = json.dumps(
                            asset["evidence"], sort_keys=True, separators=(",", ":"))
                        evidence_hash = hashlib.sha256(
                            evidence_json.encode()).hexdigest()
                        asset_id = "ip_" + hashlib.sha256(
                            f"{item['id']}|{asset['type']}|{asset['name'].casefold()}".encode()
                        ).hexdigest()[:24]
                        reusable_ip_writes += connection.execute(
                            """INSERT INTO reusable_ip_assets
                               (asset_id,opportunity_id,name,asset_type,maturity,
                                evidence_json,evidence_hash,recorded_at,updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?)
                               ON CONFLICT(asset_id) DO UPDATE SET
                                 maturity=excluded.maturity,
                                 evidence_json=excluded.evidence_json,
                                 evidence_hash=excluded.evidence_hash,
                                 updated_at=excluded.updated_at""",
                            (asset_id, item["id"], asset["name"], asset["type"],
                             asset["maturity"], evidence_json, evidence_hash,
                             now, now),
                        ).rowcount
                    if item.get("outcome_pricing"):
                        terms = {
                            "opportunity_id": item["id"],
                            "success_definition": item["outcome_success_definition"],
                            "attribution_method": item["outcome_attribution_method"],
                            "exclusions": item["outcome_exclusions"],
                            "fee_cap_cents": item["outcome_fee_cap_cents"],
                            "unit_fee_cents": item["outcome_unit_fee_cents"],
                            "human_escalation_rule": item["human_escalation_rule"],
                        }
                        terms_json = json.dumps(
                            terms, sort_keys=True, separators=(",", ":"))
                        terms_hash = hashlib.sha256(terms_json.encode()).hexdigest()
                        term_id = "outt_" + terms_hash[:24]
                        existing_terms = connection.execute(
                            """SELECT terms_hash FROM outcome_pricing_terms
                               WHERE opportunity_id=?""", (item["id"],)).fetchone()
                        if existing_terms and existing_terms[0] != terms_hash:
                            raise ValueError("outcome_pricing_terms_conflict")
                        connection.execute(
                            """INSERT OR IGNORE INTO outcome_pricing_terms
                               (term_id,opportunity_id,success_definition,
                                attribution_method,exclusions_json,fee_cap_cents,
                                human_escalation_rule,terms_hash,recorded_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            (term_id, item["id"], item["outcome_success_definition"],
                             item["outcome_attribution_method"],
                             json.dumps(item["outcome_exclusions"], sort_keys=True),
                             item["outcome_fee_cap_cents"],
                             item["human_escalation_rule"], terms_hash, now))
                else:
                    unchanged += 1
                digest = payload_hash(item)
                source_index = item.get("source_index", index)
                rid = receipt_id(item["id"], "eligible", item["action_mode"], source_index, digest)
                receipt_writes += connection.execute("""INSERT OR IGNORE INTO opportunity_receipts
                    (receipt_id,opportunity_id,decision,reason,source_index,payload_hash,recorded_at)
                    VALUES (?,?,?,?,?,?,?)""", (
                        rid, item["id"], "eligible", item["action_mode"], source_index, digest, now)).rowcount
            for rejected in result["rejections"]:
                rid = receipt_id(rejected.get("id"), "rejected", rejected["reason"],
                                 rejected["index"], rejected["payload_hash"])
                receipt_writes += connection.execute("""INSERT OR IGNORE INTO opportunity_receipts
                    (receipt_id,opportunity_id,decision,reason,source_index,payload_hash,recorded_at)
                    VALUES (?,?,?,?,?,?,?)""", (
                        rid, rejected.get("id"), "rejected", rejected["reason"],
                        rejected["index"], rejected["payload_hash"], now)).rowcount
                if (rejected.get("id")
                        and rejected.get("observed_at")
                        and rejected["reason"] in TERMINAL_SCREEN_REASONS):
                    row = connection.execute(
                        "SELECT pipeline_state,observed_at,payload_json "
                        "FROM opportunities WHERE id=?", (rejected["id"],)).fetchone()
                    target_state = ("expired"
                                    if rejected["reason"] == "opportunity_expired"
                                    else "unqualified")
                    expired_now = (
                        target_state == "expired"
                        and rejected.get("expires_at")
                        and parse_time(rejected["expires_at"], "expires_at")
                        <= parse_time(now, "recorded_at"))
                    newer_observation = (
                        rejected["observed_at"] > row[1] if row else False)
                    current_observation = (
                        rejected["observed_at"] >= row[1] if row else False)
                    if (row and (current_observation or expired_now)
                            and target_state in PIPELINE_TRANSITIONS.get(row[0], set())):
                        payload = json.loads(row[2])
                        payload["pipeline_state"] = target_state
                        if newer_observation:
                            payload["observed_at"] = rejected["observed_at"]
                        payload["latest_screen_reason"] = rejected["reason"]
                        evidence_id = (
                            "expiry:" if target_state == "expired" else "screen:") + rid
                        tid = transition_id(
                            rejected["id"], row[0], target_state, evidence_id)
                        connection.execute(
                            "UPDATE opportunities SET pipeline_state=?, "
                            "observed_at=?,payload_json=?,updated_at=? WHERE id=?", (
                                target_state,
                                rejected["observed_at"] if newer_observation else row[1],
                                json.dumps(payload, sort_keys=True,
                                           separators=(",", ":")),
                                now, rejected["id"]))
                        connection.execute("""INSERT OR IGNORE INTO opportunity_transitions
                            (transition_id,opportunity_id,from_state,to_state,evidence_id,
                             evidence_hash,recorded_at) VALUES (?,?,?,?,?,?,?)""", (
                                tid, rejected["id"], row[0], target_state,
                                evidence_id,
                                hashlib.sha256(evidence_id.encode()).hexdigest(), now))
                        written += 1
        return {"opportunities_written": written, "opportunities_unchanged": unchanged,
                "receipts_written": receipt_writes}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Screen and rank paid-work opportunities")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--database", help="persist decisions to the opportunity ledger")
    args = parser.parse_args()
    if args.max_age_days < 1:
        raise SystemExit("max-age-days must be positive")
    raw = sys.stdin.read().strip()
    data = json.loads(raw or "[]")
    payloads = data if isinstance(data, list) else data.get("opportunities", [])
    if not isinstance(payloads, list):
        raise SystemExit("opportunities must be a list")
    result = ingest(payloads, max_age_days=args.max_age_days)
    if args.database:
        result["persistence"] = persist(result, args.database)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
