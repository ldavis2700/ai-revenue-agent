# Lifecycle Notification Audit → Managed Service

**Mastery status:** learned and implementation-ready; not yet validated by a paid engagement.

This playbook turns a bounded, read-only lifecycle-notification diagnostic into a safe implementation pilot and, only after verified results, a recurring managed service. It is provider-neutral and applies to push, in-app, email, and SMS systems where consent and channel rules permit.

## Ideal customer profile

Best fit:

- A launched mobile app or SaaS product with real users and basic event tracking.
- Transactional or ad hoc notifications already exist, but lifecycle coverage is incomplete.
- The buyer can provide a product owner and read-only access or sanitized exports.
- The team wants measurable activation, retention, or re-engagement improvements without immediately replacing its notification provider.

Strong triggers include stalled activation, inconsistent onboarding, rising opt-outs, duplicate or mistimed sends, broken deep links, poor environment separation, and unclear ownership of notification logic.

Do not qualify a prospect when the requested outcome depends on unsupported specialist credentials, prohibited outreach, unavailable evidence, or production changes that cannot be reviewed and rolled back.

## Bounded paid diagnostic

The current market-test offer is a four-hour audit capped at **$160**. This is a calibration price, not evidence of a proven market rate or paid-client outcome.

The diagnostic includes:

1. A 30-minute evidence and goals review.
2. A read-only inventory of lifecycle moments, triggers, suppressions, channels, deep links, and owners.
3. A consent, environment, and measurement risk review.
4. A prioritized gap matrix and implementation backlog.
5. A concise findings report with a pilot recommendation and acceptance criteria.

The audit does **not** include live sends, production configuration changes, credential rotation, provider migration, or claims of revenue lift.

## Qualification and access gate

Confirm before accepting work:

- Product, user lifecycle, target outcome, and decision owner.
- Notification providers and channels in scope.
- Existing event taxonomy and source of truth.
- Consent, preference, unsubscribe, and quiet-hour behavior.
- Development, staging, and production separation.
- Available delivery, engagement, conversion, complaint, and opt-out metrics.
- Current campaign/automation ownership and rollback authority.
- Whether evidence can be supplied through read-only access or sanitized exports.

Start with the least privilege possible. Prefer screenshots, exports, and read-only roles. Never request credentials in chat or store secrets, raw device identifiers, full message bodies containing personal data, or unrelated customer records in the evidence pack.

## Audit workflow

### 1. Establish the measurement contract

For each stated goal, record:

- Baseline period and population.
- Primary metric and guardrail metrics.
- Attribution window.
- Known confounders.
- Minimum observation period.
- Data owner and evidence source.

If a trustworthy baseline is unavailable, recommend instrumentation first. Do not promise or price against an outcome that cannot be independently measured.

### 2. Build the lifecycle matrix

Use one row per notification opportunity:

| Field | Purpose |
| --- | --- |
| Lifecycle moment | Activation, habit formation, retention, recovery, renewal, or win-back |
| User state | Eligibility and segment definition |
| Trigger event | Verifiable source event |
| Delay/window | Timing, timezone, quiet hours, and expiry |
| Suppressions | Opt-out, conversion, duplicate, frequency, legal, and safety gates |
| Channel | Push, in-app, email, or SMS |
| Message intent | User benefit and single action |
| Deep link | Valid destination and fallback |
| Environment | Development, staging, or production |
| Owner | Approver and operator |
| Primary KPI | Measurable success criterion |
| Guardrail | Opt-out, complaint, error, or fatigue ceiling |
| Rollback | Disable path and accountable owner |

### 3. Review safety and reliability

Check:

- Opted-out or ineligible users cannot be targeted.
- Test users and environments cannot leak into production audiences.
- Duplicate events, retries, and race conditions are idempotent.
- Deep links resolve to authorized, valid destinations with fallbacks.
- Frequency caps, quiet hours, and local time are explicit.
- PII, secrets, and raw device identifiers are absent from logs and evidence.
- Failed sends and provider errors are observable.
- Every automation has an owner, disable switch, and rollback procedure.

### 4. Prioritize gaps

Rank each candidate by user value, evidence quality, reach, expected effort, reversibility, compliance risk, and measurement readiness. Recommend only the smallest set that can produce a clean learning signal.

### 5. Validate the evidence pack

Run the repository's read-only validator:

```bash
python scripts/notification_audit.py path/to/redacted-audit.json
```

The validator checks opt-out suppression, environment separation, deep-link coverage, evidence completeness, metric definitions, and redaction. It is an internal implementation sample, not evidence of client work or business results.

## Diagnostic acceptance criteria

A diagnostic is complete only when the buyer receives:

- Current-state lifecycle matrix.
- Consent, privacy, environment, and ownership findings.
- Prioritized gap list with rationale.
- KPI and guardrail definitions.
- Pilot scope with explicit exclusions.
- Rollback and incident-response requirements.
- Redacted evidence pack that passes the validator or a documented explanation for each unresolved failure.

## Implementation pilot

A pilot should contain one to three reversible automations, use staging or a controlled cohort first, and require buyer approval before production enablement.

Minimum pilot gates:

- Events and audience eligibility verified.
- Opt-out and suppression tests pass.
- Deep links and fallback behavior pass.
- Test/prod isolation is demonstrated.
- Logging and alert ownership are assigned.
- Holdout or baseline comparison is defined.
- Disable and rollback paths are exercised.
- Production send authority remains with the buyer unless a separate, explicit authorization exists.

Use fixed or bounded pricing until delivery effort is known. Record labor, tooling cost, rework, and support time to calculate contribution margin.

## Managed recurring service

Only offer recurring operations after a successful, accepted pilot. A monthly service can include:

- Trigger and journey health checks.
- Suppression, deliverability, and deep-link monitoring.
- A controlled experiment cadence.
- Incident triage and rollback preparation.
- Monthly KPI, guardrail, and learning report.
- Quarterly lifecycle roadmap refresh.

Keep production approvals and consequential changes behind the client's designated owner. APEX may prepare and validate actions, but should not send campaigns or change production settings without explicit scope and authorization.

## Pricing and evidence ladder

1. **Diagnostic:** bounded fee for read-only findings and backlog.
2. **Pilot:** fixed or capped implementation with acceptance tests.
3. **Managed service:** recurring fee based on verified operating effort and service level.
4. **Outcome/value component:** consider only after a reliable baseline, auditable attribution, and successful recurring delivery exist.
5. **Productization:** consider only after multiple repeatable, positive-margin engagements reveal a stable common workflow.

Do not count a proposal, contract value, invoice, platform balance, or pending transfer as revenue. Record revenue only after payment is settled and verified; record contribution margin only after direct delivery costs and owner effort are reconciled.

## Retention and expansion

Expansion should follow verified customer need, not assumed ROI. Legitimate paths include additional lifecycle moments, another consented channel, stronger monitoring, analytics integration, and recurring experiment operations. Stop or narrow the service when guardrails deteriorate or incremental value cannot be measured.

## Mastery evidence gates

- **Learned:** this playbook and validator exist.
- **Validated:** at least one paid engagement is accepted and payment settles.
- **Repeatable:** multiple engagements meet acceptance criteria with positive contribution margin.
- **Scale candidate:** acquisition and delivery remain positive after realistic sales, support, and owner-effort costs.
- **Productize candidate:** repeated workflows and data boundaries are stable enough for reusable software.

Current status remains **learned**. No paid-client validation, repeatable economics, attributable lift, or collected revenue is claimed.
