# APEX self-improvement operating loop

This release implements a **bounded self-review stage** inside the existing
`revenue_worker.py` loop. It does not create a duplicate automation, alter the
owner's schedule, provision a host, write application code autonomously, or
silently deploy changes.

## Goal

Continuously improve APEX's execution **quality, reliability, revenue
conversion and verifiable economics**, not its number of speculative models or
reports. Work toward the user's indefinite wealth-building objective, preserving
their stop/pause controls and all provider, payment, publishing, and spend gates.

## What runs

The worker adds `self_review` after its existing learn, plan and authorized
inbound stages. `scripts/self_improvement_cycle.py` looks at up to 50 recent
local worker cycles and writes **one durable review per UTC day** into the
existing private revenue SQLite database. Repeat worker cycles return the
existing record. The review chooses exactly one testable bottleneck:

- **Reliability:** repeated failed/timed-out/interrupted stages or malformed
  run history; propose a reproducible synthetic test and reviewed fix
- **Runtime observability:** absent/empty persistent cycle history; verify
  actual host uptime, locks, state and heartbeat
- **Collection coverage:** missing receipt schema/data coverage; independently
  verify linked provider and source
- **First paid delivery:** no local receipts; prioritize real consented buyer
  demand, tested acceptance and authorized non-Stripe settlement
- **Realized profitability:** local receipts exist; independently reconcile
  settlement, fees, refunds, delivery/support costs, retention and owner cash

The review **does not** call remote services, contact customers, purchase
resources, accept terms, publish media, or mutate unrelated project databases.
It never copies raw diagnostic strings, customer data or credentials into its
summary. A status like `completed` is a completed worker stage, not a sale.
Missing receipt tables mean collection coverage is unverified, not that the user
earned $0. Local receipt rows are not proof of provider settlement.

## Follow-through requirements

At each scheduled connected agent run, read the most recent improvement review
from an actually accessible trusted runtime, together with genuine buyer
messages, repository CI, and permitted provider receipts. Prioritize paid
fulfillment and customer support; then choose the highest-value independent
safe reversible fix. Create a focused branch/PR, run relevant and full tests,
verify deployment eligibility, release through actual provider approval, then
re-check the original defect. Do not close the task merely because a plan,
draft PR or CI run exists. Treat blocked external work as a reason to pursue
other productive authorized steps, not a reason to remove safety controls.

If the revenue worker is not itself deployed, this stage cannot be claimed
to run autonomously in production. Validate the actual deployment, persistent
DB, recovery, logs and economic data before declaring continuous operation.
Neither a periodic ChatGPT automation nor an enabled repository workflow is
proof of an always-on execution process.

## Validation

`python -m unittest discover -s tests -p 'test_self_improvement_cycle.py' -v`

Tests cover single daily writes, idempotence, failure prioritization, zero
receipt reasoning, absent data, malformed stages, privacy, immutable daily
reviews and correct placement inside the existing worker.
