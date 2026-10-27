# APEX Business Model: Compliant Vacant-Land Wholesaling

Status: approved for research, qualification, and deal preparation. Contract execution, earnest money, title commitments, and closing remain deal-level consequential gates.

## Model

Identify potentially underpriced vacant land, verify ownership and constraints, negotiate a lawful purchase agreement that expressly permits assignment when allowed, and assign the contractual interest to a qualified end buyer for a disclosed fee—or use another attorney/title-company-approved structure.

Revenue is recognized only after a closing agent confirms the assignment fee has settled. Leads, signed contracts, expected fees, escrowed funds, withdrawable funds, and money received must remain separate ledger states.

## Hard compliance gate

Before activity in any jurisdiction, APEX must record current primary-source answers for:

1. Whether wholesaling, marketing an equitable interest, brokering, assignment, double closing, or transaction-based compensation requires a real-estate license.
2. Mandatory seller and buyer disclosures, including disclosure that the wholesaler is not the property owner and is marketing only a contractual/equitable interest.
3. Advertising restrictions and required wording.
4. Contract, cooling-off, cancellation, earnest-money, escrow, title, tax, and closing requirements.
5. State and federal telemarketing, Do-Not-Call, TCPA, email, privacy, and data-broker restrictions.

If rules are unclear, conflicting, or counsel/closing-agent approval is unavailable, the market is blocked. APEX must not provide legal advice, act as a broker without authority, market property it does not own, conceal its role or fee, forge signatures, pressure vulnerable owners, misstate value, use misleading “cash buyer” claims, or send mass unsolicited outreach.

## Opportunity workflow

### 1. Market qualification

Score candidate markets by regulatory clarity, assignment acceptance by reputable title/closing providers, recorded transaction volume, parcel liquidity, data quality, buyer depth, average days to close, and complaint/enforcement risk. Prefer one well-understood jurisdiction over broad national outreach.

### 2. Property discovery

Use lawful public records and authorized listing/data sources to identify vacant parcels. Capture parcel ID, legal description, owner of record, tax status, access, zoning, utilities, flood/wetlands, liens, HOA/POA, environmental constraints, comparable sales, listing history, and source timestamps.

Never scrape contrary to site terms, bypass access controls, or infer sensitive personal facts.

### 3. Conservative underwriting

Estimate a defensible resale range from comparable closed sales, then subtract closing/title costs, taxes/liens, holding or double-close costs, required diligence, uncertainty reserve, buyer margin, and the proposed disclosed assignment fee.

Reject parcels with uncertain ownership, unusable access, unclear legal description, unresolved title defects, unverifiable comps, environmental red flags, or margins that fail a documented downside case.

### 4. Seller contact

Contact only through lawful, consent-respecting channels. Check suppression, opt-out, Do-Not-Call, prior-contact, frequency, and identity-disclosure requirements before every message or call. Use individualized, truthful communication; honor opt-outs immediately. Do not automate personal phone calls, impersonate the owner, or claim a guaranteed closing.

### 5. Contract gate

Before signature, require:

- verified seller identity and authority;
- attorney/title-company-reviewed form for the jurisdiction;
- explicit assignability or approved alternative structure;
- required wholesaler/equitable-interest and fee disclosures;
- objective inspection/diligence and cancellation terms;
- exact earnest-money amount, escrow holder, deadlines, and remedies;
- no custom or consequential term accepted without owner approval.

APEX may prepare a deal packet and draft terms but may not sign, bind the owner, deposit earnest money, or open escrow without the required deal-level approval.

### 6. End-buyer qualification

Use consented investor relationships, permitted marketplaces, or a compliant buyer list. Verify identity, acquisition criteria, proof of funds where appropriate, closing history, and non-discriminatory selection. Share only the minimum necessary property and contract-interest information.

### 7. Closing and revenue verification

Use a licensed title company, closing attorney, or escrow provider as required. Reconcile the executed assignment/double-close documents, settlement statement, fees, taxes, refunds, and payment status. Count revenue only when the closing provider confirms settled funds attributable to the transaction. Never count projected spreads, signed-but-unfunded contracts, or escrow deposits as revenue.

## Funnel states

`discovered → researched → compliant_market → seller_contact_eligible → contacted → replied → qualified_seller → underwritten → owner_approval_required → contracted_interest → buyer_marketing_eligible → qualified_buyer → assigned_or_double_close → closing_pending → settled → reconciled`

Terminal states include `opted_out`, `unqualified`, `compliance_blocked`, `title_failed`, `cancelled`, and `expired`.

Every transition stores evidence, timestamp, jurisdiction, responsible party, next deadline, and reversible next action.

## Unit economics

Track per deal:

- acquisition/contract price;
- verified resale or buyer price;
- assignment fee or gross spread;
- data, communication, diligence, title, escrow, legal, and closing costs;
- earnest money at risk;
- probability-adjusted net value;
- time to contract, buyer, closing, and settled cash;
- lead-to-contract, contract-to-close, cancellation, complaint, and opt-out rates.

Pause a channel if realized margin, compliance risk, complaint rate, or time-to-cash underperforms the recorded threshold.

## Autonomous actions allowed

APEX may research laws from primary sources, qualify markets and parcels, build conservative underwriting, maintain suppression and audit records, prepare individualized drafts, assemble deal packets, and rank buyers and opportunities.

Owner-only or consequential gates include identity attestations, licensing decisions, legal advice/signatures, seller purchase-contract execution, earnest money, opening escrow, custom legal terms, title commitments, property acquisition, and closing authorization.

## Executable research-only pipeline (issue #213)

`scripts/land_research.py` turns caller-supplied parcel records into a deterministic,
source-linked dry-run scorecard. It intentionally has no connector for outreach,
advertising, offers, contracts, signatures, deposits, purchases, or paid data.

The default policy in `config/land_research_policies.json` contains no approved
jurisdiction. A jurisdiction may become `RESEARCH_ONLY_APPROVED` only after a
human legal review records current primary-source URLs for licensing, marketing,
assignment, contracts, telemarketing, and disclosures. Research approval still
does not authorize an external action.

Input records must identify a permitted public/licensed source, its record and
terms URLs, observation timestamp, and affirmative terms/robots/collection
review. The pipeline normalizes jurisdiction/county/parcel IDs, keeps the freshest
duplicate, expires stale records, accepts only verified closed-sale comps, excludes
price-per-acre outliers, requires legal road access and title evidence, and
subtracts closing, diligence, legal/assignment, carrying/marketing, taxes/liens,
and uncertainty reserve from the conservative supported value.

```bash
python3 scripts/land_research.py parcels.json \
  --policy config/land_research_policies.json > land-research-dry-run.json
```

The output separates `discovered`, `verified_comp`, and `verified_buyer` research
stages. It reports verified settled deals and revenue only when a caller supplies
an explicitly verified closing receipt with an HTTPS evidence URL and external
transaction ID. Projected spreads remain `projected_value_is_revenue=false` and
the aggregate projected-revenue field stays zero. Government-buyer claims fail
closed unless a fresh, specific procurement URL and solicitation ID are present.

`tests/test_land_research.py` covers duplicates, misleading asking/listing comps,
missing road access/title evidence, disallowed markets, stale or unauthorized
sources, unsupported government-buyer claims, conservative economics, and strict
settled-revenue separation.
