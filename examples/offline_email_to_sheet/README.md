# Offline email-to-sheet reliability demonstration

This **synthetic-only demonstration** processes local JSON representing authorized inbound email into an atomic local CSV snapshot. It is not connected to Gmail, Google Workspace, Google Sheets, n8n, any client, or any external API. It does not send, archive, delete, or respond to email; all follow-up records require human approval.

## Reproduce

```sh
cd examples/offline_email_to_sheet
python3 -m unittest discover -p 'test_pilot.py' -v
python3 pilot.py --input messages_demo.json --output-dir /tmp/apex-email-sheet-pilot
python3 pilot.py --input messages_demo.json --output-dir /tmp/apex-email-sheet-pilot
python3 pilot.py --input messages_demo.json --output-dir /tmp/apex-email-sheet-pilot --inject-failure
```

The first run writes `synthetic_sheet.csv` and `execution_log.json`. The replay is idempotent. Failure injection preserves the prior sheet rather than partially adding a row; the execution log records the failure. Dangerous spreadsheet formula prefixes in untrusted strings are escaped.

**Scope not claimed:** Real-world Google OAuth, production API retries, concurrent-worker races, quotas, alert delivery, privacy compliance, monitoring or handover are **not** implemented. Before any client pilot: obtain a funded agreement and client-authorized limited test inbox/sheet, define approved field mapping and retention, implement least-privilege OAuth and encrypted token storage, server-side idempotency, API throttling and failure alerts, manually review outbound/destructive actions, then demonstrate both success and failure paths for the authorized owner. No pricing, personal experience or paid customer outcome is implied by this sample.
