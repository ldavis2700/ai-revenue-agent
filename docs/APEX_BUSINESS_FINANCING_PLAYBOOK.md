# APEX Business Credit & Capital Acquisition — preparation lane

**Status:** Offline preparation capability only, **not deployed** as an autonomous loan applicant. Do not claim a lender has been contacted, that funding is available, or that APEX can secure approval without lender underwriting.

## Daily operating loop (existing APEX worker only; no duplicate scheduler)
1. Preserve higher-priority paid customer delivery and currently authorized revenue work.
2. Review each owner's **real, existing** business separately. Never invent entities or build fictitious histories. A polished business profile is persuasive only when material claims have evidence.
3. Compile authorized, nonsensitive facts: legal business name, registered status, owner-confirmed industry and purpose, operating history, products, market, actual customer traction, source-linked revenue/cost/debt numbers, and requested capital use. Mark each claim *documented*, *owner_attested*, or *missing*.
4. Research official SBA programs and actual CDFIs, microlenders, credit unions and banks; record source URL, access date, program constraints, rates, fees, geography, collateral, guarantees, credit inquiry policy, loan minimum/maximum, and verified lender identity. Never infer that a search hit is a genuine lender or that a borrower qualifies.
5. Compare **repayment ability, total cost and downside risk** before comparing maximum loan amounts. Explicitly model conservative cases, actual existing debt service, contingent guarantees, and cash-flow shortfalls; if not documented mark unresolved.
6. Generate an owner-review packet: accurate business summary, non-fabricated financial overview, use-of-funds budget, source-linked evidence index, gaps, financing options with exclusions and any actual written lender feedback.
7. Owner-specific explicit consent is required before a lender inquiry that discloses private data, prequalification/credit pull, any application, paid service, guarantee, contract, or drawdown. Never circumvent KYC, lender terms, identity verification or credit restrictions. Never send repeated unsolicited lender submissions.
8. Log research provenance, decisions and verified outcomes in the **existing** APEX records (no new ledger or duplicative task). Report measured progress, not imagined approvals or funding.

## Offline readiness checker
Run only with an authorized local JSON file containing nonsensitive, factual business data:

`python scripts/business_financing_readiness.py /private/approved_business_facts.json --output /private/readiness_report.json`

Fields: `legal_business_name`, `entity_type`, `state`, `industry`, `business_description`, `operating_since`, `use_of_funds`, `requested_amount`, `annual_revenue`, `annual_net_income`, `existing_annual_debt_service`, `source_documents`. The `evidence` object maps each field to `{"status":"documented","source":"private_reference"}` or `{"status":"owner_attested"}`. Missing evidence is a gap, not confirmation. Never commit input/output files containing actual business details or personal financial data.

Do not pass SSNs, EINs, DOBs, account numbers or tax documents into this tool. If a lender later needs such materials, use its trusted secure portal after explicit owner authorization and the lender's instructions.

## Lender source anchors (check current rules at every review)
- https://www.sba.gov/loans/7a-loans/
- https://www.sba.gov/loans/microloans/
- https://www.sba.gov/loans/lender-match/

Microloans cannot be used to buy real estate or refinance debt; SBA Lender Match is not a loan application or loan guarantee. Real-estate flips are not eligible uses for SBA-approved loan proceeds via Lender Match. APEX must keep speculative REO/wholesaling separate from business operating-capital financing.

## Acceptance before automation expansion
Pass unit tests; document an authorized representative's approval mechanism; prove no outbound calls or hard credit checks; maintain evidence and access controls for sensitive materials; review full lender terms with owner; validate the actual deployed worker version. Merging this change does not by itself activate an hourly research process.

## Integration checkpoint (Nov 13, 2026)

The proposed branch now adds `('financing_readiness', 'scripts/business_financing_cycle.py')`
to the existing `revenue_worker.py` stage list **after** authorized inbound, planning,
and market research. This is a once-per-UTC-day local-only readiness check using the
same revenue SQLite database for **state and missing-item count only**. A missing
`APEX_FINANCING_PROFILE_PATH` is a harmless unready state; no fake company profile
is generated. Configure the optional path only to an owner-authorized local JSON
file outside source control, never inside a public repository. Merely running the
cycle does not research live lenders, query financial accounts, submit applications
or authorize any private-data sharing. The existing scheduled research workflow
can independently evaluate currently published lender options and prepare a sourced
owner review.

Generate a human-readable, evidence-labeled financing profile packet locally:

`python scripts/business_financing_packet.py /private/approved_business_facts.json --output /private/financing_packet.md`

No claimed lender approval, automatic underwriting or funding is implied. Do not
place private packet contents in PR comments, CI artifacts, analytics or worker logs.
The packet is *only* a preparation document; real eligibility and affordable loan
terms must be confirmed by the actual lender and owner.

Tests added: `tests/test_business_financing_readiness.py`,
`tests/test_business_financing_cycle.py`,
`tests/test_business_financing_packet.py`. Validate the whole worker CI suite and
the actual deployed commit before treating the addition as live.
