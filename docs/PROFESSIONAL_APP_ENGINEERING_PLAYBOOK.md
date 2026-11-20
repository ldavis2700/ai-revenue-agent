# APEX Professional App Engineering Playbook
Version: 2026-11-14 | Status: ON-DEMAND REFERENCE ONLY; not a deployed autonomous builder

## Invocation policy — owner request required
This is an **on-demand skill library**, not an autonomous goal, standing business model, continuous workflow, periodic research assignment, or background app-building job. APEX may consult or execute this playbook **only in response to an explicit owner request for app design, development, testing, or maintenance**. Do not autonomously seek app-development clients, generate app concepts, propose new app projects, design screens, edit app code, schedule app-design tasks, or route leads into app-building work by virtue of this guide. Do not add it to revenue_worker, Mission Control, hourly/daily automations, task queues, or self-directed work selection. Existing owner-directed project schedules and tasks are not changed by this document; this guide does not authorize new activity. Any future integration must enforce this invocation gate in actual code, not merely in prompts.

## Mission and definition of done
Build original, accessible, secure, maintainable, commercially useful apps with verifiable requirements, tests, deployments, and measurable user outcomes. Never confuse a generated prototype with production readiness, an approved PR with a deployed app, an app-store upload with approval, or a paid invoice with settled revenue.

## 1. Product discovery before code
1. Identify an actual user, pain point, current workaround, value proposition, and measure of success.
2. Write a one-page PRD: target users, user journeys, scope and exclusions, acceptance criteria, constraints, dependencies, privacy needs, and release target.
3. Separate must-have MVP workflows from nice-to-haves. Prototype the riskiest assumption first; reject features without demonstrated user benefit.
4. Evaluate competitive alternatives, distribution, pricing, onboarding, retention, and support costs. Do not fabricate demand, revenue, or customer feedback.
5. Define nonfunctional goals with measurable budgets: latency, reliability, accessibility, security, cost, recovery, and supported device/browser versions.
6. For client projects, require permission, a verified scope and contract, payment terms, ownership/IP terms, source handoff, maintenance responsibility, and agreed acceptance tests before execution.

## 2. User experience and design systems
- Map onboarding, happy paths, errors, empty states, offline states, permissions, cancellation, upgrade, deletion, and recovery.
- Start with flows and wireframes, then reusable components and tokens for spacing, typography, color, and motion.
- Design for keyboard/screen readers, dynamic text, contrast, touch targets, focus order, semantic labels, reduced motion, and localization.
- Test navigation with real devices and representative users; minimize signup friction and avoid dark patterns.
- Build loading and failure UI deliberately: never let a stalled request resemble completed success.

## 3. Choose architecture by constraints
- Web: choose simple server-rendered or static sites for content/lead capture; adopt client-side SPA complexity only when justified. TypeScript, component testing, accessible HTML, responsive layout, and progressive enhancement are useful defaults.
- iOS/Android: prefer the existing repository's framework and validated build pipeline; Flutter can share UI across platforms, but native entitlement, push, deep-link, billing, background, and accessibility behavior need platform-specific tests.
- API: version interfaces; validate requests and responses; paginate; document errors; apply idempotency to retries and payment/webhook events.
- Data: design ownership, schema migrations, indexes, backups, retention, deletion, and least-privilege access before rollout. Never expose admin credentials in clients.
- Prefer modular monoliths to premature microservices. Document decisions and tradeoffs with short ADRs. Avoid technology migrations without measured payoff.

## 4. Professional implementation standards
- Source control: small scoped branches, descriptive commits, reviewed PRs, required checks, dependency pinning/lockfiles, reproducible builds, and release tags.
- Code: cohesive modules, explicit interfaces, validation at boundaries, typed domain models, consistent error handling, minimal dependencies, maintainable naming, and useful comments explaining why.
- Use configuration/environment variables for nonsecret settings and a managed secrets store for credentials. Do not commit secrets or production data.
- Treat AI-generated code as untrusted until checked by tests, security review, and manual inspection. Never claim tools or integrations work merely because code exists.
- Document onboarding and operational runbooks: setup, env vars without secret values, local test, deploy, rollback, and troubleshooting.

## 5. Security, privacy, and trust
- Perform a lightweight threat model covering users, assets, abuse cases, auth, storage, API exposure, billing, and admin operations.
- Use supported authentication providers, secure sessions, authorization on **every** privileged backend action, role checks, and tenant isolation; authentication alone never proves authorization.
- Enforce input validation, contextual output encoding, parameterized queries, CSRF protections where applicable, SSRF restrictions, upload content/type/size limits, rate limits, and abuse controls.
- Encrypt data in transit; protect sensitive data at rest; minimize collection; redact logs; define retention/export/deletion paths; verify backup and recovery.
- Check dependency and secret scanning, mobile signing configuration, content moderation, and store/account rules before submission.
- Billing: distinguish store IAP/Google Play Billing from eligible external payments based on current official policy, region, and product; do not bypass platform requirements.
- Do not automate contact scraping, unsolicited messages, purchases, legal attestations, payouts, or irreversible account changes without required consent and authorization.

## 6. Testing pyramid and release gates
Before declaring a feature done, attach evidence for:
- Unit tests: domain logic, validation, price calculations, permissions and failures.
- Integration tests: auth, persistence, third-party boundaries, migrations, queue/retry/idempotency, and webhook verification.
- End-to-end tests: signup/login/logout/password recovery, core task, billing sandbox, support, deletion, and interrupted network.
- Security tests: unauthorized cross-user access, upload lifecycle, leaked secrets, abuse/rate limits, replay, and subscription lifecycle.
- UX/accessibility: assistive tech, keyboard navigation, dynamic text, contrast, small screen, slow network, and explicit error states.
- Release: staging against realistic synthetic data, exact commit provenance, CI green, migration rehearsal, rollback strategy, backup restore exercise, smoke checks and observability.
- Mobile: real-device coverage, app permissions, signing/certificates, privacy manifests/disclosures, screenshots, age/content ratings, review credentials, TestFlight/internal testing, store listing consistency.
If any critical gate fails, status is **blocked** and the failed gate plus reproducible evidence is recorded. Never fabricate pass results.

## 7. Delivery and production operations
1. Requirement and accepted design -> issue tickets -> implementation branch -> tests/CI -> review -> staging -> approval gate -> production rollout.
2. Use feature flags, gradual rollout, versioned migrations, health checks, logs, request IDs, alerts, crash reporting, latency/error dashboards, and known rollback steps.
3. Distinguish **committed**, **merged**, **built**, **deployed**, **store-submitted**, **store-approved**, **publicly available**, and **verified functioning** as separate factual milestones.
4. Track activation, conversion, retention, churn, crashes, support burden, accessibility issues, infrastructure spend, contribution margin, and refunds. Avoid vanity metrics as proof of success.
5. After release, triage actual user reports, close the loop, and prioritize safe improvements based on severity and measured impact.

## 8. Owner-requested app services only: scope-first, evidence-first
Only when the owner explicitly requests evaluation of app-development services, possible offerings include a paid MVP prototype, bug-fix sprint, responsive business site, internal workflow app, mobile app maintenance, testing/accessibility audit, and post-launch support. These are **candidate** offerings, not live services or proof of market demand.

For each owner-authorized app-development engagement (do not automatically source or pursue app-development leads):
- Verify user authorization, specific outcome, technical feasibility, budget, timing, hosting, platform requirements, and access restrictions.
- Record deliverables, explicitly excluded work, acceptance tests, milestone prices, revision limit, privacy/security obligations, ownership/handoff, third-party costs and maintenance terms.
- Start with a paid discovery or bounded pilot where uncertainty is high. Never promise guaranteed store approval, specific income, unlimited revisions, or zero operating cost.
- Estimate using expected engineering/test/review hours + infra and provider fees + risk reserve; accept only if realistic contribution margin and owner authorization permit.
- Keep all invoices, actual payment settlements, deliverable hashes, QA logs, acceptance evidence and revenue claims linked to the existing APEX ledger; do not create a second unverified sales ledger.
- Never ship client IP into public demos or publish client data. Use synthetic data for portfolios.

## 9. On-demand execution loop (only after explicit owner request)
```
owner request -> classify requirements and risks -> propose smallest valuable change
-> locate existing tests and policy gates -> branch -> implement -> run tests
-> evaluate security/accessibility -> PR for review -> approved release
-> verify actual deployment -> monitor outcomes -> record evidence -> repeat
```
This document does **not** activate those capabilities or permit continuous/background app-development work. Each step must be backed by connected tools, authorized credentials, allowed execution settings, and recorded evidence. Failed calls, uncertainty, or insufficient permissions must remain visible. Respect all owner pause/stop controls and existing hourly automation schedules; this playbook never modifies them.

## 10. Project-specific application when owner requests the skill
- **HAEVEN**: prioritize restored-user data integrity, auth, media upload/retrieve/delete and cleanup acceptance, moderation/account deletion, subscription lifecycle, production routing, iOS replacement validation, then Android release. Keep original/live and HAEVEN 4 tracks distinct until independently verified.
- **APEX**: make its own app/admin interface secure, useful, observable, persistently accessible to the owner, and capable of showing grounded status, receipts, errors and intervention requests. Separate agent reasoning from actual tool execution and authorization.
- **RMC CLASSICS**: test multiplayer synchronization, state consistency, reconnection, rematch, share actions, iOS review account, privacy disclosures and device screenshots before resubmission.
- **Life Quest**: design fun missions that create verified real-world progress; don't reward fabricated milestones or manipulate engagement. Test child safety/age suitability, privacy, moderation, and ads policy.

## 11. Learning syllabus and practice sequence
1. Product thinking: customer interviews, PRDs, metrics, prioritization; exercise: PRD and testable acceptance criteria.
2. Design: Figma-equivalent workflows, components, accessibility; exercise: responsive screens and usability test.
3. Frontend: HTML/CSS/JavaScript/TypeScript or Flutter/Dart; exercise: auth-aware interactive form with failures.
4. Backend: HTTP, typed APIs, validation, job queues; exercise: versioned CRUD API with authorization.
5. Data: relational/document modeling, migrations/indexes, retention; exercise: backup/restore and deletion test.
6. Security: OWASP threats, tenancy, session management, privacy; exercise: cross-user access prevention test.
7. Quality: unit/integration/E2E, CI, accessibility and performance; exercise: CI gate blocking defective PR.
8. Operations: deployments, secrets, monitoring, rollbacks, incident playbooks; exercise: staging release + rollback.
9. Commerce: subscriptions, sandbox webhook verification, refunds, taxation/accounting handoff; exercise: idempotent payment lifecycle test.
10. Delivery: contracts, estimates, maintenance, handoff; exercise: scope-limited sample statement of work.

## 12. Source-of-truth habit
Before coding, re-check current official framework, security, accessibility and app-store docs (Apple Developer, Android Developers/Google Play, Flutter, OWASP, W3C WCAG) for policy/API changes. Cite dated primary references in technical decisions. Never assume this static playbook overrides newer official requirements.

## Minimum progress report
Report: objective; exact repo/branch/commit; changed files; tests executed and outcomes; security/privacy impact; deployment URL and commit if verified; store state if applicable; blocked gates; next safe action; customer/revenue evidence if any. Use **unverified** rather than inference when source evidence is missing.
