# APEX owner controls (local CLI)

The owner/operator—not the autonomous agent—has final authority. This change is a deliberately small first step toward an authenticated owner command center.

## Commands on the worker host

```sh
python owner_control.py status --db /files/data/revenue_agent.db
python owner_control.py pause --db /files/data/revenue_agent.db
python owner_control.py resume --db /files/data/revenue_agent.db
python -m unittest tests.test_owner_control -v
```

Pause creates the same persistent `<database>.pause` marker already checked by `revenue_worker.py` during every stage and between cycles. Resume only removes that marker; **it cannot override** `REVENUE_AGENT_KILL_SWITCH=true`. Status reports the marker, kill-switch state, and the worker's existing heartbeat health. Mutations append a minimal audit entry to `<database>.owner_audit.jsonl`.

## Scope and security

- This CLI **does not** authenticate remote users and must **not** be exposed directly through a public HTTP endpoint or chat command.
- Run it only in the worker's trusted, access-controlled runtime with the same database mount. The host/operator permissions are the authentication boundary for this iteration.
- Changes do **not** create new permissions for spending, contracts, charging, outbound messaging, credential access, or self-modifying code.
- The audit log is local and records actions, not credentials or customer details. Production needs retention, centralized audit, and RBAC before a public dashboard exists.
- This controls the **APEX revenue worker only**, not every independent APEX/HAEVEN scheduler or content service.
- An environment kill switch is authoritative and can only be changed through the deployment's secured configuration.
- The repo commit is a proposed improvement until merged, deployed, tested in the worker host, and matched against the running deployment SHA.

## Follow-on acceptance criteria
1. Run unittest and integration tests on the target worker runtime.
2. Exercise pause mid-stage and confirm its subprocess group terminates and no new action runs while paused.
3. Verify resume works without bypassing the kill switch.
4. Confirm operator permissions, persistent volume, and audit file handling.
5. For remote owner control, design an authenticated API with MFA, RBAC, CSRF protection, idempotent commands, and independent approval gates; never reuse this local CLI as a public endpoint.
