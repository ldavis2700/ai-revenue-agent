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

## Official lender-program desk research — checked November 14, 2026 UTC

**No applicant data supplied, no lender approached, no financing outcome verified.** These are public program facts, not eligibility findings. The proposed borrower, jurisdiction, actual operating history, documented cash flow, authorized capital use, exact fees, guarantees and offers remain unresolved.

| Research option | Current published parameters | Limits, costs and owner-review gate | Official evidence |
| --- | --- | --- | --- |
| SBA 7(a) via approved lender | Up to $5 million; eligible business needs and credit, use of funds and location are evaluated by the lender | Rates negotiated subject to program maximums; borrower may bear an upfront guarantee fee, plus permitted lender/agent fees; check **FY2027** fee notice and obtain itemized term sheet before any affordability claim | https://www.sba.gov/loans/7a-loans/ |
| SBA Microloan intermediaries | Up to $50,000; small-business working capital, supplies and equipment; current borrower page says maximum 7-year term | Generally 8%–13% interest as an indicative range, **not a quote**; no real estate purchase or existing-debt refinancing; credit, collateral, guarantees and fees depend on the actual intermediary | https://www.sba.gov/loans/microloans/ |
| SBA Lender Match | Can connect business to interested SBA lenders; it is **not a loan application nor guarantee** | Completing the questionnaire discloses personal information to prospective lenders; owner-specific approval is required **before** submitting even a match request | https://www.sba.gov/loans/lender-match/ |
| Community-development lenders | OFN offers a **free** directory of member CDFIs; geographic coverage and products vary | Directory membership does not prove certification, product availability or qualification; verify the named lender's own official rates, fees, licenses, geography and credit-inquiry requirements | https://www.ofn.org/cdfi-locator/ |

**Conflicting Microloan term references (checked November 14, 2026):** The [current borrower-facing SBA Microloan page](https://www.sba.gov/loans/microloans/) and the [March 31, 2026 SBA explanation](https://legacy.sba.gov/article/2026/03/31/sba-microloans-offer-proven-low-dollar-financing-small-businesses) say **up to seven years**; the [older intermediary operating guide](https://legacy.sba.gov/partners/lenders/microloan-program/operate-intermediary) and [SBA lender overview](https://www.sba.gov/sba-lenders/) still state **six years**. Record both dated official sources, do not silently select whichever term improves projected affordability, and request the named intermediary's current controlling terms and written actual loan duration. If no lender terms exist, **total borrowing cost and eligibility remain unknown**, even when an illustrative interest range is published.

**Repayment assessment:** Do not calculate an eligibility score. For any documented principal and written APR/fees/term, separately show the full amortization, total dollars repaid, lender and third-party fees, debt-service coverage using **actual cash available for debt service** (not gross sales), existing obligations, and a downside case with at least a 20% decline in available operating cash flow. If any input is missing, label the result *cannot assess*, rather than filling in estimates or assuming zero. Show personal-guarantee and collateral exposures as separate unresolved risks.

**Source-date nuance (verified November 14, 2026):** [SBA's FY2027 7(a) fee notice 5000-881797](https://legacy.sba.gov/document/information-notice-5000-881797-fy-2027-7a-program-fees), effective **October 1, 2026**, governs fiscal-year fee and exception review; it is not an individual lender quote, APR disclosure or promise of a fee waiver. A FY2026 small-manufacturer fee waiver expired September 30, 2026; never carry that discount forward into FY2027 without a new official notice. Obtain the actual dated fee schedule and an itemized, binding lender disclosure before calculating total cost. A 2026 SBA rule reportedly permits eligible combined 7(a)/504 borrowing up to $10 million, which is **not** a $10 million single 7(a) loan or an eligibility determination. Source: https://www.sba.gov/sba-newsroom/2026/05/18/sba-doubles-cumulative-7a-504-loan-limit-10-million/

**Current next action:** Validate private owner-authorized records before constructing entity-specific packets. Keep any private records and generated reports off GitHub; preserve only status/gaps in the existing APEX database. Do not submit lender inquiries, take credit checks or borrow without separate explicit authorization.

## Named CDFI / community-lender desk review — November 14, 2026

**Research only.** These are published **lender advertisements, not quotes or borrower eligibility determinations**. California entity registration, service-county presence, operating financials, owner guarantee consent, credit history and the specific legal use of funds must all be independently documented. Do not send any personal or business financial records, request prequalification, trigger an inquiry, submit an application, or pay a fee without transaction-specific owner authorization. Verify every item again on the official lender site before making a decision.

| Candidate, official source | Published geography and product | Advertised rate and charges | Unresolved borrower-specific gate |
| --- | --- | --- | --- |
| [Pacific Community Ventures — Small Business Community Loan](https://www.pacificcommunityventures.org/get-a-loan/) | California businesses **operating and generating revenue for at least 12 months**; **$10,000–$500,000**, one-to-seven-year loan; one month interest-only | **8.75% fixed**, **3.5% closing fee**, no prepayment penalty; personal guarantee required from **each owner with more than 20% ownership** | **Real-estate industry excluded** among other exclusions; actual industry, operating and revenue history, location, use of funds, owners/guarantees, cash available for debt service and written offer unknown |
| [Accessity — Start-up and Expansion Loans](https://accessity.org/loans/) | Southern California business/owner geography; **$300–$25,000** or **$25,001–$250,000**; published terms **12–48 months** and **12–84 months** respectively | **8.99%–14.99% advertised fixed simple-interest range**; no application fee or prepayment penalty; closing costs normally **financed in the loan**, approx. **6.5% above $5,000** (see conditions) | Service county, legal entity, personal financial obligations, ability to repay, exact APR, financed fees and lender quote unknown |

**Accessity source discrepancy:** Its [FAQ](https://accessity.org/faqs/) still describes general loan terms as 12–72 months while the [product page](https://accessity.org/loans/) describes up to 84 months for the larger product. Ask the lender for a dated, product-specific written maximum before including a term in amortization. **Financed closing charges can increase principal and total interest**, so do not estimate total cost by simply adding a one-time fee to the advertised rate. The quoted lender fees and interest are not a disclosed borrower-specific APR; compare written APR, payment schedule, origination/third-party costs, collateral, personal guarantees, early payoff, and downside cash flow. Pacific Community Ventures' guarantee condition is material owner risk; do not assume the owner's consent.

**Status:** Two new named lender options researched; **0 borrower-specific screens completed, 0 applications, 0 credit inquiries, 0 lender contacts, 0 lender approvals, 0 funds received**. If there are no owner-authorized repayment facts, the readiness result must remain **CANNOT ASSESS**. Loan proceeds must never be booked as collected sales revenue.

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
