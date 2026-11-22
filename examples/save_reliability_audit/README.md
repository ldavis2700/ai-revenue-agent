# Synthetic save reliability and concurrent-edit QA proof

**Status: offline tested sample only — NOT a deployed Supabase/Next.js integration, buyer audit, proposal, or paid delivery.** Uses only Python standard library and a temporary SQLite database. It never calls an API, sends a message, changes production storage or consumes paid credits.

A 2026-11-21 authenticated Upwork listing requested evidence of failed saves and concurrent edit loss in a Next.js/Node/Supabase application. This small original proof demonstrates a narrower, useful invariant: **never claim a save was persisted unless a transaction committed and a separate readback verified its revision and contents**. It does not pretend to diagnose an unseen customer's code, RLS policy, websocket state, or Supabase production behavior.

Run the test harness and sample:

```bash
cd examples/save_reliability_audit
python3 -m unittest -v test_save_audit.py
python3 save_audit.py
```

The sample tests a persisted successful save, a stale concurrent edit refused without silent overwrite, transaction rollback on simulated storage failure, exact-request idempotency, rejected key reuse, invalid input, missing record, and two competing threads. It uses `BEGIN IMMEDIATE` and a revision predicate. A failed/indeterminate write must be reconciled before a retry or customer-facing success message. A replay of a transaction whose committed receipt is still `committed_pending_readback` must be reconciled, **not** interpreted as proven saved. This is deliberate fail-closed behavior.

**Limitations and real-buyer prerequisites:** SQLite is not PostgreSQL; no service integration, end-user permissions, authenticated session, RLS, real network timeouts, browser UI, error telemetry, provider acknowledgment, or operator acceptance exists here. A real audit requires authorized repository/log access, reproduced failing test, transaction and frontend state traces, relevant RLS/trigger/schema review, privacy controls and an approved remediation/QA scope. If a save returns an unknown outcome after a network timeout, reconcile the persisted request ID/version before retrying; never overwrite the latest edit. No identifiable user data belongs in a public sample or issue.

**Business state:** researched and locally demonstrated skill preparation only. No new experiment admitted, Upwork Connects consumed, client contacted, contract won, amount charged, paid receipt, fee, settled payout or positive net contribution verified.
