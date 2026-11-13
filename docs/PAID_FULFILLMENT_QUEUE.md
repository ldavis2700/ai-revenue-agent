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
automated consumer, refund reconciliation and delivery credentials are
still required before unattended fulfillment can be enabled; this migration does
not enable external sending, create a new charge or claim a sale has been delivered.

Validation uses disposable PostgreSQL: replayed payments, setup and renewal work,
foreign-property exclusion, unmatched buyers, atomic rollback when queue insertion
fails, and server-only permissions. Never insert these fixtures into production.

### Queue schema: lease fields are on the existing queue

The production migration named `paid_preparation_leases` **does not create a
standalone `public.paid_preparation_leases` table**. It adds lease, attempt,
blocker, and durable preparation checkpoint columns and the four service-role
RPCs to `public.paid_fulfillment_queue`. Do not query a guessed leases table:
that returns relation-not-found and does not inspect real funded work.

For a read-only, server-authorized triage, count obligations first, including
blocked and prepared-but-not-delivered work:

```sql
SELECT status,
       count(*) AS obligations,
       count(*) FILTER (WHERE preparation_token IS NOT NULL) AS leased,
       count(*) FILTER (WHERE prepared_at IS NOT NULL) AS prepared
FROM public.paid_fulfillment_queue
GROUP BY status
ORDER BY status;
```

An empty result means no rows **in that queue at that read time**, not that no
customer, payment, refund, or claim exists elsewhere. Prepared items still
require independently authorized delivery; do not re-claim or silently
count them as delivered. Inspect joined signed payment and consented buyer
evidence before making any claim or external action. Never expose service
credentials, buyers, identifiers, or artifacts in a public issue.

## Preparation reservations and recovery

Authorized server workers must use the following RPCs when preparing paid work.
These are SECURITY INVOKER functions, executable only by the service role. Public
clients cannot access them. Keep that credential on trusted servers only.

- `claim_paid_preparation(p_worker, p_lease_seconds=600)` atomically reserves one
  oldest eligible obligation and returns its row. Concurrent workers skip locked
  rows. An empty result means no eligible preparation, not that all work is done.
- `renew_paid_preparation(p_event_id, p_token, p_lease_seconds=600)` extends a
  current lease. Durations are bounded to 60–3,600 seconds.
- `finish_paid_preparation(p_event_id, p_token, p_sha256, p_artifact_ref)` checkpoints
  the completed private artifact and clears the lease. Store the actual artifact
  durably first, then record its hash and reference. This leaves the obligation
  pending delivery; preparation is never counted as delivery or revenue.
- `block_paid_preparation(p_event_id, p_token, p_reason)` preserves a concrete
  missing dependency and excludes the obligation from automatic claiming.

All mutations require the unexpired token returned for that specific attempt. A
false result means stop and inspect the current row; do not continue using an old
lease. After a claim timeout, inspect the queue for that run's unique worker ID
before retrying: the claim might have committed. After a finish timeout, read the
checkpoint and compare the exact artifact/hash before deciding whether to retry.
Use a distinct worker ID per run. Tokens and worker IDs are internal state.

A crashed preparation is reclaimable after expiry with a fresh token. At five
attempts it becomes blocked on the next claim cycle, requiring investigation.
Only after resolving the reason may an authorized operator reset attempts to zero,
clear the blocker, and return it to pending. Do not blindly reset retry limits.
Prepared artifacts are preserved and excluded from further claims. The database
checks evidence format; the operator must verify its actual contents and storage.

**These leases cover reversible preparation only. Never perform a customer send,
charge, or other external side effect under them.** Expired preparation may replay.
External delivery still needs provider idempotency, uncertain-outcome reconciliation,
current payment/refund/dispute checks, verified scope and destination, and a
separate delivery claim. Keep unattended delivery disabled until those are ready.
Existing trusted service-role operators retain table privileges; they must use the
RPCs rather than overwrite lease fields directly. This is coordination among
trusted workers, not isolation against a compromised service-role credential.

Additional disposable PostgreSQL tests cover active/expired/stale workers, durable
checkpoints, dependency blockers, bounded retries, privilege checks, and eight
concurrent sessions claiming distinct work while another session holds a row lock.

## Supervised setup preparation adapter (source only; not deployed)

`python -m scripts.paid_preparation_consumer` is an opt-in, server-only bridge
from signed APEX setup receipts to the existing offline 14-response builder.
It is **not** scheduled and is disabled unless both `--execute` and
`APEX_PAID_PREPARATION_ENABLED=true` are present. It must run only on an
authorized trusted server with `SUPABASE_URL` fixed to the existing APEX project,
`SUPABASE_SERVICE_ROLE_KEY`, and a restricted live `STRIPE_SECRET_KEY`. Do not
put those values into GitHub, public clients, command lines, logs or test fixtures.
A paid invoice for the optional managed service is **not** handled by this
setup-only adapter.

Before even claiming, the operator must obtain and independently validate
each buyer's paid scope and verified five-field business profile. Put one
private `evt_*.json` dossier per signed event under a directory with mode
0700. It must contain exactly grounded profile facts, the matching event and
lead IDs, `scope_accepted: true`, `business_facts_verified: true` and an
HTTPS `scope_evidence_url` to the actual authorized acceptance record. These
boolean attestations and URLs are *operator-provided*, not themselves proof
that a buyer agreed. Never manufacture them or trust a lead's free-text field
as a customer contract. Confirm the actual purchaser, delivery channel,
deadline, refund policy and permitted purpose outside the script.

The consumer reads the oldest eligible pending setup before it can claim.
It refuses missing dossiers, unmatched property-003 receipts and lead hashes,
a different business name, any unconfirmed scope, any non-$100 setup event
and Stripe Checkout without an expanded succeeded PaymentIntent, paid
undisputed/unrefunded charge, matching live payer email, amount and currency.
Only then may it claim via the PR255 bounded server-side lease. It builds a
private ZIP using the PR247 builder, verifies its included checksums, flushes
the private files to the existing persistent volume and renews before
checkpointing through `finish_paid_preparation`. A false/expired finish
never counts as success. A finish timeout is reconciled against the exact
artifact reference and SHA-256, not blindly retried.

For the current Railway /data volume, create **private**, non-web-served
directories `/data/private-paid-dossiers` and
`/data/private-paid-preparations` with mode 0700, verify the source and
operator evidence, then invoke with:
`python -m scripts.paid_preparation_consumer --execute --dossier-root /data/private-paid-dossiers --artifact-root /data/private-paid-preparations`.
Do not enable this in the persistent hourly worker or provider configuration
until trusted credentials, the dossier intake, validated genuine payment,
private volume and acceptance safeguards have passed production preflight.
Never use synthetic production receipts or live test charges.

The result `prepared_not_delivered` means **only** that a draft artifact
was privately checkpointed; it is not payment settlement, buyer acceptance,
customer contact or a completed delivery. External delivery requires a
separate idempotent consumer, renewed refund/dispute checks, an independently
verified recipient and scope, a provider receipt and failure reconciliation.
The existing `DELIVERY_ENABLED=false` remains controlling. Keep both the
prepared artifact and payment ledger private, and inspect real obligations
before acquisition each cycle.
