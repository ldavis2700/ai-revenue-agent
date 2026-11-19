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

Both financing command-line tools require an **absolute path to an existing regular profile JSON file outside the repository**, owned by the invoking account, with no group/world permissions or symlink path components. Keep the input file owner-only (`0600` on POSIX systems) and the output private. The CLI rejects unsafe paths before reading private contents. This is a local privacy safeguard, not an authorization to submit borrower records.

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

## November 16, 2026 — additional official program comparison (research only)

This dated review adds cost and time-to-cash distinctions to the **existing** lender-readiness record; it does not open a parallel ledger, add a scheduler, perform a credit check or contact a lender. Public product claims are not borrower-specific offers, and eligibility, actual APR, fees, cash available for debt service, total repayment and lender availability remain **unverified** for any APEX-associated entity.

| Official program | Public terms reviewed November 16, 2026 | Cash-flow / permission implications |
| --- | --- | --- |
| [Kiva U.S. community lending](https://www.kiva.org/borrow) | Advertises **$1,000–$15,000**, **0% interest, no borrower fees or collateral**, no minimum credit score, and repayment generally **12–36 months**. [Eligibility and process](https://www.kiva.org/borrow/small-business-loans) describe public crowdfunding and a private-supporter fundraising stage; typical application review **20–25 business days**, then supporter and public fundraising phases. | **Not instant cash**; not suitable as a same-day revenue substitute. Requires actual business eligibility, verified repayment capacity, PayPal access and an owner-approved public fundraising/disclosure decision. Never invite supporters, publish a borrower profile, link payment accounts, apply or promise acceptance without transaction-specific owner approval. |
| [Accion Opportunity Fund SBA 7(a) loan](https://aofund.org/business-loans/sba-small-business-loan/) | Advertises **$100,000–$350,000**, variable interest **from Prime + 2.25%**, **3% loan fee**, terms up to **10 years for working capital**. Lists 2 years of business/personal tax returns, business debt schedule, interim financials, SBA forms and organizational records as required application materials. | Higher-documentation product; the rate floats and advertised fees alone **do not establish total cost**. Do not provide confidential records, prequalification responses or applications without explicit owner approval. Evaluate this only after documented operating cash flow and a real use-of-funds budget, then obtain a written APR/fee/guarantee/collateral schedule. |
| [SBA Microloan program](https://www.sba.gov/loans/microloans/) via [official intermediary list](https://www.sba.gov/loans/microloans/list-of-microlenders/) | Up to **$50,000**; published general interest range **8%–13%**; borrower-facing SBA page says a **seven-year maximum term**, while older official lender references say six. | The named intermediary makes the underwriting/term decision. Obtain a written product-specific term and fee disclosure; no real-estate purchases or refinancing existing debt. No inference of qualification from presence in the lender directory. |
| [SBA 7(a) program / FY2027 fee notice](https://legacy.sba.gov/document/information-notice-5000-881797-fy-2027-7a-program-fees) | Published notice is **effective October 1, 2026** and defines FY2027 SBA lender/guaranty fees and exceptions. | It is **not** a borrower APR or a lender quote. Check the current actual fee rule, permitted lender fees and any borrower passed-through upfront fee on a real written offer. |

**Risk and readiness sequencing:** Preserve paid-customer job-to-cash work as the first APEX revenue priority. Before any financing pursuit, assemble only an owner-authorized private factual entity profile with sourced revenue, net profit, operating cash available for debt service, existing repayment obligations, entity jurisdiction and permitted use of proceeds. If missing, mark **CANNOT ASSESS** and research only. Compare principal plus financed origination/closing charges, amortizing payments, variable-rate stress, 20% lower operating cash flow, collateral/personal-guarantee exposure, and all third-party costs against actual cash availability. A 0% advertised interest rate does not mean a loan can fund immediately or that repayment is affordable. No loan proceeds belong in the **collected sales revenue** ledger.

**Verified production checkpoint — November 18, 2026, 17:20 Pacific (supersedes older undeployed status):** [PR #285](https://github.com/ldavis2700/ai-revenue-agent/pull/285) is merged, and live Railway `apex-content-worker` deployment `f19a9fcb-a8dd-4f08-a695-295c90897b70` is **SUCCESS** at source `fa4e6e2c2a96959dd90a7c089a95f47f45617d93`. The exact deployed `revenue_worker.py` contains `('financing_readiness', 'scripts/business_financing_cycle.py')` after authorized inbound and public research. Runtime log cycle **#668**, completed at **2026-11-19T01:13:43Z**, lists this stage as completed; external customer delivery remains **disabled**. This proves the *local-only readiness stage executes*, **not** that an owner-authorized borrower profile exists, an application has been sent, a credit report pulled, or eligibility/repayment established. The `APEX_FINANCING_PROFILE_PATH` variable was absent from the inspected service variable-name inventory. No private applicant profile, confidential finance figures, or loan parameters are committed here.

**Fresh primary-source recheck (November 18, 2026):**
- [SBA Microloans](https://www.sba.gov/loans/microloans/): up to **$50,000**, generally **8%–13%**, borrower-facing **up to seven years**; must be an eligible U.S. small for-profit operating business, with intermediary-specific underwriting. No property purchases or refinancing of existing debt. Separate older lender-oriented SBA pages may say six years; obtain the current lender's written maximum term.
- [SBA 7(a)](https://www.sba.gov/loans/7a-loans/): up to **$5 million** for authorized purposes, subject to lender underwriting, program eligibility, rate caps, fees, guarantee and collateral requirements; not a business-specific offer.
- [FY2027 7(a) fee notice](https://legacy.sba.gov/document/information-notice-5000-881797-fy-2027-7a-program-fees): **effective October 1, 2026**, not the earlier one-year FY2026 manufacturer waiver. Never infer the applicant's current total fee from a general notice alone.
- [SBA Lender Match](https://www.sba.gov/loans/lender-match/) and [OFN CDFI Locator](https://www.ofn.org/cdfi-locator/): **research only**. Lender Match shares applicant information with prospective lenders and does not guarantee a match or an offer; the CDFI directory is free and does not establish a loan product, written rate, approval, or certified lender status.

**Remaining readiness and owner-only gates:** Before a borrower-specific packet can be trusted, privately verify legal entity and state, operating history, documented revenue/net income, cash *available for debt service*, all existing debt service, exact use of proceeds, lender principal/APR/fees/maturity, collateral and guarantee risk. A missing or unsubstantiated input means **CANNOT ASSESS**: no inferred loan qualification, no filled-in $0 obligations, no fictitious rates or payment ability. If complete, compute full repayment and a 20% lower cash-flow scenario privately under the evidence controls. Written rates/fees, including third-party charges, and consent/soft-vs-hard inquiry details must be verified for each named lender. **Explicit transaction-specific owner approval is required before any data disclosure, lender match request, application, credit inquiry, fee, guarantee, signature or borrowing.** Borrowed money is never earned revenue.

**Release reconciliation:** Railway has **no staged changes** in the inspected APEX environment. Current GitHub `main` is **nine commits ahead** of the deployed worker `fa4e6e2c…`, chiefly offline demos/docs; these source differences are **not** proof of new production behavior. Revalidate exact source, CI, volume persistence and rollback before any future worker rollout. Preserve existing hourly execution and owner stop controls; do not create a duplicate financing scheduler.
