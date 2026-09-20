# Consignment dashboard delivery playbook

> **Evidence boundary:** This is a reusable design and QA asset. It is not evidence of a paid engagement, client deployment, marketplace integration, or collected revenue.

## Intended offer

A bounded paid pilot that turns an inconsistent consignment spreadsheet into:

1. one authoritative item and sale ledger;
2. client-isolated, mobile-first status and payout views;
3. auditable approval requests for price or advertising changes;
4. a human-reviewed payout-preparation workflow; and
5. an operating baseline that can become a managed weekly service.

The pilot does **not** move money, purchase advertising, scrape marketplaces, or promise live synchronization unless a supported source API/export is separately verified and authorized.

## Qualification checklist

Proceed only when all answers are acceptable:

- The buyer controls the Google, portal, Shopify, and marketplace accounts.
- Each consignor has a stable internal ID and a verified delivery address for their portal link.
- The source of truth for sold date, gross sale amount, refunds, marketplace fees, and return status is named.
- The client defines commission splits, allowed fee types, rounding, and the 30-day return-window rule in writing.
- A funded milestone covers one portal template, one revision round, QA, handoff, and documentation.
- Acceptance criteria exclude unsupported marketplace automation and bulk historical cleanup.
- Row/user isolation is supported by the selected portal; a public link is not an acceptable privacy control.
- Any approval action records intent only. A separate authorized human executes spend or payout actions.

Reject or re-scope when credentials must be shared insecurely, data ownership is unclear, approval buttons would trigger irreversible spend, financial calculations cannot be reconciled to source records, or the requested scope cannot fit the funded pilot.

## Canonical data model

Use immutable IDs and separate facts from derived views.

### Consignors

| Field | Purpose |
|---|---|
| consignor_id | Stable internal identifier |
| display_name | Portal-facing name |
| verified_email | Access and delivery identity |
| verified_phone | Optional delivery/recovery identity |
| split_rate | Contracted consignor share |
| portal_status | invited, active, suspended, closed |
| created_at | Audit timestamp |

### Items

| Field | Purpose |
|---|---|
| item_id | Stable internal identifier |
| consignor_id | Owner relationship |
| title | Client-facing item name |
| category | Reporting segment |
| intake_date | Custody timeline |
| status | intake, authenticating, ready, live, sold, returned, paid |
| list_price | Current authorized price |
| marketplace | Named selling channel |
| listing_url | Direct listing reference |
| photo_url | Approved client-facing image |
| source_updated_at | Last authoritative update |

### Sales and payouts

| Field | Purpose |
|---|---|
| sale_id | Stable sale identifier |
| item_id | Sold item |
| sold_at | Authoritative sale timestamp |
| gross_sale | Gross amount |
| marketplace_fees | Source-backed fees |
| approved_ad_fees | Fees approved in the audit log |
| other_deductions | Contract-authorized deductions |
| refund_amount | Confirmed refunds |
| return_window_days | Contracted hold period |
| clears_at | Derived review date |
| payout_status | pending, eligible, held, paid, reversed |
| consignor_amount | Derived amount, then human-reviewed |
| paid_at | Payment evidence timestamp |
| payment_reference | Authorized rail reference; never a secret |

### Approval log

| Field | Purpose |
|---|---|
| approval_id | Immutable request ID |
| item_id | Related item |
| request_type | price_drop or ad_fee |
| previous_value | Before state |
| proposed_value | Requested state |
| plain_language_effect | What the client sees |
| requested_at | Audit timestamp |
| decided_at | Audit timestamp |
| decision | pending, approved, rejected, expired |
| actor_id | Authenticated decision maker |
| executed_at | Separate execution timestamp |
| execution_reference | Human/operator evidence |

Never overwrite an approval record. A changed proposal creates a new request.

## Calculation rules

The workbook should use named fields or protected formula columns. Illustrative logic:

```text
net_before_split =
  gross_sale
  - marketplace_fees
  - approved_ad_fees
  - other_deductions
  - refund_amount

consignor_amount =
  MAX(0, ROUND(net_before_split * split_rate, 2))

clears_at =
  sold_at + return_window_days

payout_status =
  IF(refund_amount > 0, "reversed",
    IF(manual_hold = TRUE, "held",
      IF(today < clears_at, "pending", "eligible")))
```

These formulas are examples, not accounting or legal advice. The buyer must approve the contractual inputs. Marking a row `eligible` prepares it for review; it never initiates payment.

## Portal experience

Design for a client using an iPhone with minimal technical confidence:

- saved private link or authenticated magic-link entry;
- large status cards: Live, Sold, Pending, Cleared;
- a monthly payout history with gross sale, deductions, split, and net amount visible;
- one-tap item detail with image, current price, channel, and listing link;
- approval requests showing the exact before/after value and dollar impact;
- explicit confirmation before recording Approve or Reject;
- success receipt with timestamp and request ID;
- no horizontal scrolling at common mobile widths;
- no hidden status conveyed only by color.

Portal queries must be scoped by the authenticated consignor identity. Filters in a public report are not access control.

## State transitions

```text
item:
intake -> authenticating -> ready -> live -> sold -> paid
                                      \-> returned

approval:
pending -> approved -> executed
        \-> rejected
        \-> expired

payout:
pending -> eligible -> paid
        \-> held -> eligible
        \-> reversed
```

Invalid backward transitions require an explanatory correction record rather than silent history edits.

## Pilot acceptance tests

### Access and privacy

- Consignor A cannot retrieve Consignor B's rows by filtering, URL editing, cached navigation, export, or direct row lookup.
- Suspended access fails closed.
- Portal links, screenshots, logs, and documentation contain no credentials or unrelated client data.

### Ledger correctness

- A representative sold item reconciles from source gross sale through every deduction to the displayed split.
- Boundary checks cover the day before, exact instant of, and day after `clears_at`.
- Refund, partial refund, manual hold, zero/negative net, missing fee, and duplicate sale cases fail visibly.
- Currency values use consistent rounding and never rely on formatted strings for arithmetic.

### Approvals

- Repeated taps create only one decision.
- Approve and Reject require authenticated identity and a confirmation step.
- Editing a proposed value invalidates the old request and creates a new one.
- Approval does not automatically spend money or alter a marketplace listing.
- Execution is recorded separately with operator evidence.

### Mobile and accessibility

- Primary flows pass at 320px viewport width and on a physical iPhone.
- Buttons have unambiguous labels and usable target sizes.
- Keyboard navigation, focus visibility, text zoom, contrast, loading, empty, error, and retry states are verified.
- Past-month payouts are reachable without spreadsheet navigation.

### Operations and recovery

- Imports are idempotent by source identifier.
- Duplicate items and sales are flagged rather than silently merged.
- Failed updates preserve the last confirmed state and expose a retry path.
- A backup/export and restore check is documented.
- The operator SOP explains daily updates, monthly reconciliation, exceptions, access removal, and escalation.

## Delivery sequence

1. Confirm source systems, written rules, sample data, user roles, and acceptance criteria.
2. Create a redacted ten-item test fixture spanning pending, eligible, paid, held, returned, and refund cases.
3. Build the protected master schema and formula layer.
4. Configure the client-isolated portal and Shopify handoff.
5. Implement approval-request logging without spend execution.
6. Run the acceptance suite and reconcile every test fixture.
7. Conduct owner walkthrough and one revision round.
8. Deliver the schema dictionary, access map, QA evidence, backup/export, and SOP.
9. Offer managed operations only after pilot acceptance.

## Managed-service scorecard

Measure weekly:

- records updated;
- reconciliation error rate;
- stale-source exceptions;
- approval turnaround time;
- client delivery failures;
- payout rows prepared and reviewed;
- hours consumed versus cap;
- buyer-reported corrections;
- time saved, if the buyer can substantiate a baseline.

Do not claim positive margin, retention, ROI, or repeatability until a paid engagement is delivered, costs are reconciled, and payment is verified as collected.

## Productization path

After at least two verified positive-margin deliveries with materially similar requirements:

1. freeze a versioned schema and test fixture;
2. make fee and return rules configuration-driven;
3. package portal components and SOP templates;
4. add connector adapters only for supported, authorized APIs;
5. automate reconciliation reports before automating financial actions;
6. retain human approval for spend, payouts, rule changes, and exceptions;
7. evaluate a multi-tenant SaaS only after access isolation, auditability, support burden, and willingness to pay are validated.
