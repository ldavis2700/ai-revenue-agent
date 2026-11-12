# Persistent research and revenue-work runtime

November 11, 2026 owner directive: pursue legitimate wealth through continuous research and demonstrated execution. No system can guarantee uninterrupted uptime or income.

## What the code does

The existing `revenue_worker.py` now runs primary-source discovery, experiment learning, model planning, authorized-inbound routing and self-review every 15 minutes. The research collector checks fixed official Upwork research, OpenAI news and Stripe pricing-reference sources at most every six hours. It respects robots rules, rejects redirects and nonpublic destinations, bounds bytes/time/items, and stores titles, reference URLs, publisher-provided dates and independent observation times. It never follows extracted links or runs page instructions. Publisher blocks and network failures produce an unavailable state with bounded persistent backoff; they do not refresh success dates or stop other stages.

The planner links up to two eligible catalog candidates to fresh lexical references without changing the existing evidence-based profitability order. Public references do not establish buyer demand, capability, prices, permission, earnings or mastery. The connected hourly research workflow must read the cited primary sources, compare dated buyer evidence and actual delivery/economics, then perform the next authorized acquisition or fulfillment action. This collector is source discovery, not an LLM, broad autonomous browsing or model training. Comparing the most profitable observable models still requires genuine measured outcomes; no global winner is claimed.

## Deployment on the existing host

`Dockerfile.content` includes the worker and supervisor. With `APEX_REVENUE_WORKER_ENABLED=true`, the entrypoint starts content production and the revenue-work loop in the existing container, retaining the same CPU, RAM, replica and storage allocation. State is private at `/data/revenue/revenue_agent.db`, outside public routes. `APEX_PUBLIC_RESEARCH_ENABLED=true` enables the bounded public GET requests. Both flags default off; CI's existing `--once` renderer behavior is unchanged.

`runtime_supervisor.py` forwards shutdown, terminates siblings after a child exits, and exits nonzero so the host's existing ALWAYS restart policy can recover. Existing worker single-instance locking, stage deadlines, heartbeats, crash reconciliation, delivery idempotency and pause controls remain active. Aggregate health checks the revenue worker when enabled. An intentional pause is preserved. A host outage still requires provider recovery; this is not redundant multi-host high availability.

Initial activation must leave `DELIVERY_ENABLED=false` and `REVENUE_AGENT_EXECUTION_ENABLED=false` unless a separately verified provider and buyer path is ready. The deployed content service currently has no delivery or inbound-sync credentials. Its local database must not be presented as the authoritative Supabase payment/customer ledger, and empty local tables do not prove no customers or revenue elsewhere. The persistent loop can perform research and preparation independently; external buyer work continues through authorized connected workflows until adapters are actually configured and tested. Checkout remains paused.

## Release acceptance and rollback

1. Pass Python/Node and exact-source hosted container checks. Review branch conflicts with the separate private-media/academy candidate #251; do not silently apply that candidate.
2. Stage only the tested source pin and the four flags above on `apex-content-worker`. Recheck the environment for unrelated changes before committing. Do not alter `apex-ultra-api`, resource limits, volumes or billing.
3. Observe Railway SUCCESS, public offer/privacy and aggregate health, nonpublic database paths returning 404, runtime cycle records, and actual research outcomes. A 200 response alone does not prove productive execution. Do not claim source success before observing it.
4. Confirm a later independent cycle and persistent recovery before claiming sustained operation. Verify long-term availability through recorded cycles and errors; do not promise zero interruptions.
5. Roll back to the prior source pin `004b794ae1db769a4ab8b7d164048fbc3f505f86` with the new worker flag disabled if combined service acceptance fails. Preserve `/data`, media and research evidence. A source rollback is not permission to erase unresolved delivery records.

Keep the same hourly APEX workflow enabled. It owns current demand, semantic research, buyer work, provider receipts and meaningful owner updates; no duplicate ChatGPT schedule is required.
