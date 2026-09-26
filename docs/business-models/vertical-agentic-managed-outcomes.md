# APEX Mastery Playbook: Vertical Agentic Automation + Managed Outcomes

## Thesis
APEX should treat **vertical agentic automation sold as a productized implementation, followed by a managed recurring service and selectively value/outcome-aligned pricing** as a priority business model to validate.

This is a hypothesis to test, not a guarantee of wealth. APEX must promote it only when verified unit economics and conversion evidence outperform alternatives.

## Why this model
- It sells completed business work and measurable outcomes, not generic AI access.
- It can reach revenue faster than building a standalone SaaS product from scratch.
- Reusable vertical workflows can turn one-off implementation work into repeatable delivery.
- Managed service creates recurring revenue; successful repeated delivery can later be productized into vertical SaaS.
- Outcome/value alignment can increase willingness to pay when attribution is auditable and contract terms are clear.

## Ideal customer profile
Prioritize businesses with:
1. a frequent, expensive, repetitive workflow;
2. measurable baseline economics;
3. accessible systems/APIs and an authorized data path;
4. a decision-maker who can approve a bounded pilot;
5. enough transaction volume for ROI to become visible quickly.

Examples: inbound lead qualification and booking, customer support resolution, document intake/processing, CRM follow-up, reporting/reconciliation, and other narrow workflows with explicit acceptance criteria.

## Offer ladder
### 1. Paid diagnostic / workflow audit
Map the current workflow, baseline cost/revenue leakage, integrations, risk, and a measurable success target.

### 2. Bounded implementation pilot
Automate one narrow workflow. Define deliverables, acceptance tests, rollback, privacy/security boundaries, and a fixed pilot price before execution.

### 3. Managed Agent Operations
Charge recurring fees for monitoring, maintenance, optimization, exception handling, reporting, and approved integrations. Track gross margin including model/API/tool costs.

### 4. Value/outcome component
Use only where the outcome is attributable and auditable. Define the event, baseline, attribution window, exclusions, cap/floor, refund/chargeback treatment, and evidence source in writing. Never fabricate attribution.

### 5. Productization
When multiple customers validate the same workflow, extract reusable components, templates, tests, observability, and onboarding into a vertical agent product/SaaS.

## APEX execution loop
DISCOVER -> QUALIFY -> BASELINE -> PROPOSE -> CONTRACT GATE -> BUILD -> QA -> DELIVER -> VERIFY OUTCOME -> RETAIN -> PRODUCTIZE -> SCALE.

### Discovery
Find legitimate demand from consented inbound, marketplaces, partner channels, referrals, and other platform-compliant sources. Never mass-spam or evade platform rules.

### Qualification
Reject opportunities that lack required execution capability, lawful/authorized data access, measurable value, or realistic delivery economics.

### Baseline
Before promising an outcome, record current cycle time, labor cost, error rate, conversion/revenue metric, or other relevant baseline. Mark unknowns as unknown.

### Proposal
Prefer a narrow paid pilot. State verified capabilities only. Do not claim customers, case studies, ROI, integrations, certifications, or results without evidence.

### Delivery
Use deterministic workflow code where possible and models where judgment is useful. Add validation, retries, idempotency, audit trails, human escalation for ambiguous/high-impact cases, and cost ceilings.

### Optimization
Measure:
- verified gross and net revenue;
- contribution margin after model/API/platform costs;
- time to first cash;
- pilot-to-managed conversion;
- retention/churn;
- hours of owner intervention;
- error/rework rate;
- customer outcome metric;
- payback period.

Scale only from verified observations. APEX's experiment evidence and Mission Control remain the source of truth.

## Pricing discipline
Do not race to the lowest price. Price against value and delivery risk while keeping a simple entry point.
- Diagnostic: fixed price.
- Pilot: fixed price with bounded scope.
- Managed operations: recurring base fee covering expected usage/support.
- Variable/outcome fee: optional and only with auditable attribution.

Every offer must model expected delivery cost and minimum acceptable contribution margin before it becomes a scale candidate.

## Mastery curriculum
APEX should continuously improve these capabilities:
- workflow decomposition and process mapping;
- agent/tool orchestration;
- API/webhook integration;
- n8n/automation architecture;
- retrieval and structured data extraction;
- evals, deterministic tests, and QA;
- observability, idempotency, retries, rollback;
- privacy, consent, security, and least privilege;
- vertical-specific terminology and economics;
- proposal scoping and milestone design;
- value measurement and attribution;
- recurring service operations;
- reusable productization.

## Evidence gates
A model is not mastered because it is documented. Treat mastery as earned:
- **learned**: playbook and tests exist;
- **validated**: at least one real paid engagement with verified payment and QA-backed delivery;
- **repeatable**: multiple comparable paid deliveries with positive contribution margin;
- **scale_candidate**: reliable conversion/retention and fresh, adequate sample evidence;
- **productize_candidate**: repeated workflow similarity justifies reusable software.

## Safety and authority
This playbook does not bypass existing APEX gates. No automatic spending, contract acceptance/signature, deceptive claims, unauthorized system access, unsolicited spam, production changes, or customer charges. Owner/platform approvals remain required wherever the existing runtime requires them.

## Research basis (September 2026)
APEX should periodically refresh this thesis against current market evidence. Current research points to rapid enterprise agent adoption, strong interest in customized agents, a gap between AI access and realized bottom-line value, and growing experimentation with usage/outcome pricing. The operational implication is to sell a narrow, measurable workflow outcome and retain the customer through managed operations rather than sell a generic chatbot.


## APEX issue #164 scoring and economics contract

Opportunity intake now supports explicit, evidence-supplied fields for:

- active buyer stage: prospect, qualified, proposal, buyer reply, interview, offer, or contract;
- payment-history confidence;
- measurable economic value and expected contract value;
- delivery, inference/API, and acquisition costs;
- required human operating hours;
- automation, recurring-revenue, and reusable-IP potential;
- delivery and compliance risk;
- offer phases across diagnostic, pilot, implementation, managed recurring service, outcome pricing, vertical IP, and productized agent/SaaS.

The projected unit-economics output separates contract value, cost classes,
contribution, contribution margin, and projected revenue per required human
hour. It is explicitly labeled `projected_not_collected`; it cannot be counted
as collected, withdrawable, or received revenue.

Outcome pricing fails closed unless the opportunity defines the success event,
attribution method, fee cap, and human-escalation rule. Non-positive projected
contribution margin is screened out. The $1,000/hour value is a bounded
effective-leverage scoring reference, not a promise or earnings claim.

## Evidence capture and stage separation

APEX records buyer progress as distinct evidence-backed states: submitted proposal,
buyer reply, interview, offer, and contract. New marketplace receipts should name
the exact stage; the older `response_received` state remains readable only for
backward compatibility. A contract can follow an explicit offer, while legacy
records retain their existing path.

Offer evidence is keyed to a declared commercial phase so a diagnostic artifact
cannot silently be presented as proof of managed recurring delivery. Reusable-IP
assets record a name, type, maturity, and auditable evidence references. The
maturity ladder is:

1. `learned`
2. `paid_validated`
3. `repeatable_positive_margin`
4. `scale_candidate`
5. `productize_candidate`

Promotion to paid validation requires verified-payment evidence. Promotion to
repeatable positive margin also requires verified-margin evidence. Scale
candidates additionally require retention evidence; productization candidates
require expansion evidence. Captured offer references and reusable-IP assets are
persisted in dedicated append-safe ledger tables with stable IDs and evidence
hashes. Captured artifacts remain labeled `captured_not_revenue`; they never
increase collected, withdrawable, or received balances.

## Realized economics

Projected economics never count as revenue. Realized economics may be recorded only
against a settled payment receipt already in the collected state. Each record
links delivery, inference/API, CAC, and human-time evidence to that payment and
derives:

- net collected revenue after provider fees;
- realized contribution and contribution margin;
- realized revenue per required human hour; and
- realized contribution per required human hour.

The record does not advance collected funds to withdrawable or received. A
payment can have only one realized-economics record; conflicting replacement
evidence fails closed and requires reconciliation rather than silent rewriting.

