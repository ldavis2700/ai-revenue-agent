# APEX continuous-operation policy and recovery

Owner directive, November 10, 2026: maintain ongoing useful revenue work, without voluntarily pausing the wealth workflow. Continue until the owner changes the instruction. Preserve deliberate stop controls, provider boundaries and spending authority.

## Operating instructions

- Work through funded delivery, buyer-requested work, qualified acquisition, original social content, collection readiness and profitability improvements in value order.
- A blocked operation blocks that operation. Record its exact dependency, then take the next independent authorized task in the same run.
- Keep a durable checkpoint of completed work, verified evidence, unresolved outcomes and the next executable action. Resume from evidence after interruption.
- Distinguish safe transient retry from unknown external effects. Inspect provider status/receipts before repeating a send, publication, charge or deployment. Use bounded retries and backoff; never spin forever.
- Recheck blocked dependencies when new evidence or the planned recheck time arrives. Do not ask repeatedly for the same approval, repeat identical failing calls, or endlessly rewrite plans.
- Preserve the hourly recurrence without an end date. Do not disable it because one task requires owner action. Honor any later explicit owner pause/stop and genuine provider suspension; do not create replacement accounts/workflows to bypass a stop.
- Report verified revenue, material completed work, real security/operational issues and unavoidable owner-only actions. Do not notify about individual prospects.
- When nothing is currently runnable, record a clear waiting state and the next scheduled check. This is different from disabling the workflow. Do not fabricate productive work or income.
- An enabled schedule, healthy HTTP endpoint or completed planning job does not prove a continuously executing agent. Track scheduled time, actual start/completion, last successful useful action and errors separately.

## Code change

Previously an unhandled exception in one delivery aborted the remainder of `autonomous_cycle.run`, losing the cycle report and internal fulfillment queue from that result.

`dispatch_recovery.py` now isolates delivery faults and continues independent actions. It commits a pending-attempt record in the existing SQLite database before calling the existing delivery adapter. The logical work key binds customer and action type so a changed payload cannot bypass an unresolved attempt. No raw payloads or credentials are added to the journal or diagnostics.

A verified committed adapter receipt permits recovery after a crash without sending again. A failed, malformed or exceptional delivery outcome stays pending and is reported as `uncertain`; later cycles do not blindly replay it. A normal blocked result releases the attempt so authorized work may resume after its dependency is resolved. Concurrent cycles cannot claim the same pending action. A journal/storage failure prevents external dispatch for that action.

The action-loader subprocess is bounded to 120 seconds. The journal uses a five-second SQLite lock timeout. Existing adapter request timeouts, dispatch caps, daily caps, source/consent checks and delivery enablement remain in force. Stop controls are also checked between actions. KeyboardInterrupt/SystemExit propagate; pending evidence survives restart.

This is continuation and duplicate-prevention logic, not a new scheduler. It does not restart ChatGPT, restart the host, change hosting configuration, add credentials or grant delivery authority. No runtime flag is enabled by importing this code.

## Uncertain-outcome recovery

1. Identify the pending logical action and its exact payload hash from the protected database.
2. Reconcile against the delivery provider using the same idempotency key and trusted receipts. Do not infer that a timeout means the provider did nothing.
3. If the existing adapter's matching committed delivery receipt is present, the next cycle returns `duplicate` and releases the stale journal record automatically.
4. Otherwise leave the action quarantined until a separately authorized reconciliation establishes the real outcome. Never clear pending records merely to improve throughput. This change intentionally provides no blind retry/delete command.
5. Continue other independent work. Report storage failures as operational blockers, and uncertain external effects as reconciliation work rather than successful delivery.

## Verification and release boundary

Offline regression covers independent work after failure, persistent quarantine, changed-payload protection, provider timeouts, committed-receipt recovery, interruption before a receipt, normal dependency recovery, missing receipts, malformed results, between-action stop controls, storage faults, concurrent claims and preservation of internal fulfillment work. These tests use synthetic records and stub transport; no real messages are sent.

This candidate is stacked on PR216's combined consent/fulfillment changes. Deploy the reviewed combined release after successful hosted checks. Do not deploy this recovery layer against a stale unrelated source tree or treat local tests as deployment evidence.

Current inspected infrastructure: the hourly APEX wealth task is enabled. APEX ULTRA has an older successful deployment with persistent `/data`; its variable inventory lacks the model/write/approval credentials referenced by its engineering workflow. Two unrelated source changes are already staged there. This recovery change does not apply those staged changes, create a paid worker, or establish nonstop execution. Runtime/provider execution and deployment must be verified separately.
