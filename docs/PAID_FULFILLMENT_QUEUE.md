# Paid customer obligations

Every new signed APEX setup receipt or managed-plan invoice recorded by
`stripe-revenue` creates one `paid_fulfillment_queue` row in the same database
transaction. If queue insertion fails, the receipt insert fails and the webhook
returns a retryable error. Payment and source-object uniqueness prevents duplicate
work. The migration also queues existing verified APEX receipts once.

The queue is server-only. It contains payment identifiers and completion evidence,
not copied contact details. Join `verified_revenue_events` and `inbound_leads`
through the recorded lead ID when preparing a customer's work. A missing lead must
remain visible and be matched from verified buyer evidence, not a guessed name or
untrusted link parameter. Payment does not establish marketing consent.

On each authorized operating run, inspect pending/blocked obligations before
prospecting. Verify current payment/refund/dispute status, agreed scope, deadline,
customer identity and an authorized delivery destination. Build the actual setup
or managed-cycle deliverable using the existing response-pack tooling. Check its
quality and deliver it through an authorized channel. Record its SHA-256, actual
HTTPS delivery receipt and delivery timestamp only after delivery is verified.
If work cannot proceed, use `blocked` with a specific reason and retry when resolved.

The database rejects `delivered` without evidence fields, but cannot independently
attest their truth. A file hash or drafted email is not proof of delivery. An
automated consumer with leases, refund reconciliation and delivery credentials is
still required before unattended fulfillment can be enabled; this migration does
not enable external sending, create a new charge or claim a sale has been delivered.

Validation uses disposable PostgreSQL: replayed payments, setup and renewal work,
foreign-property exclusion, unmatched buyers, atomic rollback when queue insertion
fails, and server-only permissions. Never insert these fixtures into production.
