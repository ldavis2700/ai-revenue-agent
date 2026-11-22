# APEX Engineering Controller — safe bootstrap (October 20, 2026)

**Status: review-only, DRY RUN. Not deployed, not a functioning AI coder, and not continuously running.**

This component is a durable local SQLite queue scaffold. It intentionally performs **no GitHub writes, AI requests, deployments, purchases, user-data access or production changes**. It is separate from APEX's legitimate revenue agent; it does not repurpose or disable its revenue mission.

## Ownership and priority
- ChatGPT's existing **hourly HAEVEN advancement automation remains the primary coordinator**. This external controller is subordinate infrastructure for durable work tracking and eventually safe delegated engineering jobs.
- HAEVEN current distributed app first; PR #89 repairs and PR #90 Emergent exit; avoid promoting HAEVEN 4. APEX revenue operation remains a separate workstream. RMC CLASSICS third.
- Pro/ChatGPT subscription is **not** an API budget. No AI API or paid worker is enabled here.

## Local dry-run checks
From repository root:

```sh
python engineering_controller/controller.py --once --db /tmp/engineering-queue.sqlite3
PYTHONPATH=engineering_controller python -m unittest discover -s engineering_controller -p 'test_*.py'
```

To simulate a persistent worker *locally*, run `python engineering_controller/controller.py --db ./runtime/engineering-queue.sqlite3`. This runs a periodic dry-run queue only; the local process is not hosted. Persist `runtime/` in a protected volume if later hosting it. It must not run concurrently with itself against the same state file without additional locking/lease logic.

## Required gates before true external 24/7 operation
1. Review this code; complete local CI validation and address GitHub Actions issue #86. Confirm queue state is persistent, lockable and monitored.
2. Verify a separate Railway/Vercel hosting option with **no unapproved paid resources**; obtain explicit hosting and OpenAI API budgets before starting a continuously billed process.
3. Implement an *isolated least-privilege read-only GitHub adapter first*; make its results independently testable with redacted logs. Do not permit arbitrary shell commands or credential exposure.
4. Add sandboxed per-task build/test workers with hard timeouts and spending caps, audit logs, concurrency leases, rate limits and circuit breakers.
5. Allow branch-only code changes after tests; production merges, payments, domain changes, database writes, app-store publishing, and infrastructure migrations remain owner approval gates.
6. Keep APEX revenue decisions separate from code deployment permissions. Track verified receipts, not impressions or invented earnings.
7. No production cutover from Emergent without authenticated source inventory, backups, restore drills, media reconciliation and real-device acceptance.

## Safety
Never place tokens in files or logs. `CONTROLLER_EXECUTE=true` deliberately fails closed. There is no autonomous API execution in this PR. No hosting provider has been charged or provisioned by this change.
