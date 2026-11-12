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
