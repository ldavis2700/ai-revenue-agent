# Dynamic portfolio review (November 15, 2026)

This MVP adds a *portfolio review* stage to the existing `revenue_worker.py` 15-minute cycle. It **does not** create another scheduler, spawn agents, claim 10–20 live businesses, or bypass higher-priority HAEVEN, funded customer work, identity, payment, account, provider, or approval gates.

## Current implementation

- Loads the existing core and expansion catalog, ranks eligible business models, and uses the existing pursuit planner.
- Writes bounded historical decisions to the worker's existing private SQLite DB (`apex_portfolio_reviews`, last 500) and tracks existing active model IDs in `apex_portfolio_active` without automatically promoting research to execution.
- No capacity record means **zero new reservations** while ranking and research continue.
- A local, private `APEX_CAPACITY_ATTESTATION_PATH` JSON file may propose 30-minute blocks for internal research and original draft preparation only, once freshness and HAEVEN, customer-work, and settlement-protection attestations pass. These self-attestations are **not** independently authenticated and confer no rights to message, spend, contract, charge, publish, deliver, or claim revenue.
- Existing hourly scheduled workflows are unchanged. Existing kill switch and worker pause controls apply to the stage.

Example optional **private**, externally validated capacity report (never commit actual operator/buyer data):

```json
{
  "verified_for_preparation": true,
  "attested_at": "2026-11-15T15:00:00+00:00",
  "free_preparation_minutes": 90,
  "haeven_priority_protected": true,
  "paid_obligations_protected": true,
  "settlement_reserve_protected": true,
  "evidence_url": "https://example.org/private-capacity-evidence"
}
```

The URL in this example is illustrative, not evidence of real available capacity. It must be independently checked against other workloads and reconciled commitments before use. Never interpret this planner output as a provider receipt or external-action authorization.

## Remaining requirements for real autonomous multi-business execution

Deploy the reviewed branch, verify worker heartbeat and later independent cycles, wire authenticated read-only provider observations and receipts, reconcile actual existing active work and bookings, add per-business authenticated adapters with explicit permissions, test idempotent intake/delivery/refunds, implement hard workload and cost metering and feedback-driven promotion/retirement, and prove paid customer outcomes and settled net contribution. Capacity should expand only against measured resources and reliable fulfillment.

Validation: `python -m unittest tests.test_dynamic_portfolio`.
