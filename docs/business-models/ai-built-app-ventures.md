# APEX: AI-built app ventures and paid app-development services

Owner authorization: November 14, 2026. This is an **on-demand monetizable skill/business-model candidate**, not a new always-on app-design task. Preserve owner instruction that generic app design is not added to APEX's autonomous continuous workflow. Existing revenue-intelligence routines may compare this candidate against other business models, but should not automatically spin up speculative app builds. Keep HAEVEN release work first, APEX revenue second, RMC Classics third.

## Two distinct revenue lanes

1. **Bespoke paid app-development services (nearer-cash hypothesis).** Seek *permitted*, real buyer requests for small, scoped mobile/web app features, debugging, integrations or MVPs. Independently review technical feasibility, rights, acceptance tests, fixed deliverables, schedule, existing project duties, payment route, platform rules and support obligation. Prepare drafts or original isolated demonstrations for credible buyers. No proposal is submitted without provider authorization and evidence; no sale is recorded without a real settled receipt.
2. **APEX-owned subscription apps (longer-horizon hypothesis).** Evaluate a single narrowly scoped problem, distribution channel and retention mechanism before coding. Validate real users' willingness to pay; review competitors and platform fees. Begin with an original, low-cost private prototype. Confirm subscription entitlement handling, cancellation/refund disclosures, account deletion, privacy/security, accessibility, store-policy compliance, analytics consent and ongoing customer support. Deploy only after QA, proper credentials, platform acceptance, and separate production authorization.

The supplied video describes rapid app creation and paywalls; it does **not** establish guaranteed income, demand, repeatable three-week launches, customer acquisition costs, or subscriber retention.

## Existing APEX integration and priority

- Use the existing `mobile_app`, `micro_saas` and `ai_automation_agency` categories in `config/business_models.json`; **do not create duplicate catalog IDs or ledgers**. Keep the existing Monday business-model-to-cash comparison and hourly APEX revenue workflow intact.
- Reuse `APEX_WEEKLY_MODEL_TO_CASH.md` for dated sources, verified buyer demand, economic evidence, and revenue-state gating. The currently open professional-engineering playbook PR #297 offers the engineering/release checklist; do not claim it is merged or deployed.
- Do not displace already accepted paid customer delivery, the $100 response offer, or the existing $750 Upwork opportunity. HAEVEN iOS/HAEVEN 4 restoration and release remain higher priority.
- App development is available when requested by the owner or backed by a verified and feasible paying buyer; this mandate authorizes *assessment and safe preparation*, not unsolicited speculative deployments or spending.

## Automated offline qualification

`python scripts/app_venture_validation.py --input /private/candidates.json` evaluates a single object or a list of evidence-bearing objects. Its standard-library-only input remains private, and its outputs authorize **only** original offline pilot preparation and QA. Passing a gate does not prove source authenticity; the operator must review evidence separately.

Required data: `candidate_id`, `lane` (`owned_subscription_app` or `bespoke_paid_app_service`), `buyer_problem`, HTTPS `buyer_evidence_url`, timezone-aware `buyer_evidence_observed_at`, affirmative evidence-use permission, `original_solution`, nonnegative estimated build hours/monthly dollar cost, acquisition channel and explicit channel permission, and four true reviewed flags (`technical_feasibility_review`, `privacy_security_review`, `platform_policy_review`, `monetization_review`). Service offers additionally require `buyer_scope_evidence_url`; subscription apps require `distribution_test_defined` and `retention_test_defined`.

For each candidate, independently verify pricing, gross-to-net economics (store fees, taxes, refunds, cloud, labor, marketing, support), willingness to pay, conversion, churn, and platform permissions. **Revenue remains unknown** until authenticated settlement, and profit until actual reconciled costs. Do not pass promotional claims as observations. Never place private buyer facts or credentials in public repository files.

## Concrete next conversion steps

1. Inspect real consented service requests already accessible through existing APEX channels; prioritize a narrowly defined customer-funded app fix or integration over speculative app production. Confirm buyer scope, deliverables, acceptance criteria, budget and approved communication/payment path.
2. Capture one dated comparable market observation and test an original solution with no new paid services. Use the existing opportunity record, not a second ledger.
3. Execute `python -m unittest tests.test_app_venture_validation -v` and run the existing repository CI. Review results before merging. Run the script on privately verified candidate inputs.
4. Advance to real client delivery only through existing consent, scope, contract, provider and QA gates. Advance a standalone app only with successful demand, distribution, retention, security and store tests. No automatic checkout activation, new charges, auto-publications, auto-merges or payout changes.

**Verification status:** This source-only branch does not establish that the hosted APEX worker imports the evaluator, that an app has been built, a buyer has paid, or a store listing has been approved. Deployment and pipeline adoption must be separately evidenced.
