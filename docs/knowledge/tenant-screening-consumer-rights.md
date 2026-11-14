# APEX knowledge module: specialty consumer reports & tenant screening

Status: **research/training candidate only**. This document does not establish a deployed revenue capability, legal expertise, or a client offering.

## Source
- Owner-provided Facebook Reel screen recording (November 13, 2026; ~42 seconds), discussing >3 consumer reporting agencies, a claimed "300+" bureaus, rental/eviction reporting, and security freezes.
- CFPB company directory: https://www.consumerfinance.gov/consumer-tools/credit-reports-and-scores/consumer-reporting-companies/companies-list/
- FTC tenant background check rights: https://consumer.ftc.gov/articles/tenant-background-checks-and-your-rights
- FTC dispute guidance: https://consumer.ftc.gov/articles/disputing-errors-your-tenant-background-check-report
- CFPB security freeze limits: https://www.consumerfinance.gov/ask-cfpb/what-is-a-credit-freeze-or-security-freeze-on-my-credit-report-en-1341/
- CFPB denied housing guidance: https://www.consumerfinance.gov/ask-cfpb/what-should-i-do-if-i-am-denied-housing-because-of-a-background-check-en-2105/

## Verified lessons versus video claims
1. Many companies beyond Equifax, Experian, and TransUnion compile consumer reports, including specialty tenant-screening agencies. The CFPB list is NOT exhaustive. Do not repeat the video's "300+" as a verified exact number.
2. A tenant report can contain eviction case information and rent payment history; records can be inaccurate, outdated, duplicated, or incomplete.
3. Consumers have report-access and dispute rights, and adverse action notices identify the screening company in qualifying cases. Time limits and remedies vary.
4. The video suggests security freezes make landlords unable to view evictions. **Do not make this claim.** Freezes are company/report-specific and exemptions apply; the free nationwide-credit freeze rule does not apply to tenant screening requests. Public court records and other data sources may remain accessible. A freeze does not delete a valid eviction.
5. Historical video screenshot of CoreLogic Rental Property Solutions is not proof of current branding, availability, or freeze policy. Verify each provider through its official current site and CFPB directory.

## Potential revenue model: consumer report navigation support (not yet authorized for commercial launch)
Possible services after legal/compliance review: a clear educational guide to specialty reporting, a provider directory, a consumer-controlled checklist for free disclosures, organization of user-provided reports, flags for possible accuracy issues, and user-reviewed draft dispute letters citing the correct facts.
**Never** guarantee an eviction removal, approval for housing, score improvement, or a result within a fixed timeframe. Never misrepresent a freeze as invisibility. Do not market 'erase your eviction' or deceptive screening bypass.
Review federal/state credit-repair, consumer-reporting, legal-services, privacy, and advertising requirements **before** selling any service or collecting fees. Do not charge for merely obtaining free statutory reports under deceptive premises; avoid advance-fee violations.

## Research and execution workflow
- **Discover:** Periodically check CFPB/FTC official guidance and provider sites; timestamp findings and link citations; watch for policy/legal changes.
- **Verify:** Record for each agency the correct business name, type of report, current consumer access/dispute process, whether any freeze is offered, and exceptions. Mark unverified fields unknown; no speculative "300+" totals.
- **Evaluate:** Use a scorecard of genuine consumer need, permitted scope, acquisition costs, handling risk for sensitive data, licensing/compliance obligations, ease of delivery, and realistic willingness to pay. Prefer helpful free public resources and compliant services.
- **Prototype:** Generate anonymized example checklists and draft letters. Human-review all legal descriptions before publishing. Never auto-send letters, dispute accurate records, or submit on a client's behalf without their verified authorization and compliance review.
- **Privacy:** Do not collect, log, or publish SSNs, dates of birth, addresses, case files, credit reports, identification documents, or client eviction data in code, prompts, analytics, or public repositories. Any future handling needs authenticated restricted storage, retention policy, deletion, encryption, and proper authorization.
- **Evaluate metrics:** Verified source freshness, provider process accuracy, clearly disclosed uncertainty, completed user-requested educational deliverables, client opt-in, support quality, true paid invoices and **collected** revenue (not projections).
- **Safety gates:** No false identity, false filings, pretexting, credit profile manipulation, malicious freezes, discrimination, or evasion of legitimate screening; no promises of guaranteed housing decisions. Escalate legal questions to a licensed professional. No unsolicited sensitive-data outreach.

## Safe consumer-oriented assistance sequence
1. Ask the consumer to identify the screening company from an adverse action notice, or direct them to the official CFPB directory.
2. Explain how the consumer can personally request a report through official channels.
3. Help them review for mistaken identity, wrong case disposition, duplicate cases, sealed/expunged information, or legally outdated negative items.
4. Prepare an accurate, evidence-based dispute **draft** only if they approve the precise content. Suggest retaining copies and tracking correspondence.
5. Explain that the agency generally investigates within 30 days, sometimes 45; applicable laws vary. Never promise an outcome.
6. If needed, point to FTC/CFPB complaint options and qualified housing/legal-aid professionals.

## Deployment acceptance criteria (all required before claimed as operational)
- Workflow exists in runnable APEX scheduling/dispatch code and respects existing priority/cadence.
- Unit tests cover accurate vs inaccurate records, frozen report limitations, explicit consent, adverse-action rights, refusal of guaranteed removal, and sensitive-data handling.
- Sources have last-verified timestamps and fallback when unavailable.
- Production deployment SHA matches reviewed commit; worker logs show execution.
- Any paid offering passes legal review, security controls, billing tests, and actual collection reconciliation.
