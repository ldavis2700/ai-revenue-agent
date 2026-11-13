# Evidence-to-approval micro-pilot (fictional, offline)

A small reusable **pre-sales demonstration** for APEX's document-to-structured-record service. It is not a customer deliverable, proof of a paid order, a production product, or a live Supabase connection. The fake supplier evidence is invented for testing. It does not process customer data or contact anyone.

### Demonstration

Requires Python 3.10+ and only the standard library. From this directory:

```bash
python research_evidence_demo.py --db /tmp/apex-fictional-pilot.sqlite ingest --input fictional_input.json
python research_evidence_demo.py --db /tmp/apex-fictional-pilot.sqlite pending
python research_evidence_demo.py --db /tmp/apex-fictional-pilot.sqlite export
python research_evidence_demo.py --db /tmp/apex-fictional-pilot.sqlite review --record-id fiction-001 --decision correct --reviewer "Human demo operator" --corrected-value "4 business days"
python research_evidence_demo.py --db /tmp/apex-fictional-pilot.sqlite export
python -m unittest -v test_research_evidence_demo
```

The first export contains no approved records. After the operator's explicit correction, export contains only the accepted value plus its original source label, optional `source_url`, and SHA-256 evidence digest. When a public HTTPS source URL is supplied, the digest also binds that URL. Unsafe non-HTTPS, credential-bearing, localhost/internal, fragmented, and custom-port URLs are rejected. No source is fetched or authenticated, and a supplied link is not proof of truth. Existing local demo databases gain the nullable-by-default text field without dropping decisions. Re-ingesting changed evidence for the same ID fails closed. Repeated identical decisions are idempotent; changing a completed review requires a new evidence record. No automatic approval, production webhook, cloud transmission, email, API key, or deployment is involved.

### Buyer-scoped paid pilot handoff (not yet performed)

Only after a funded contract and written scope: obtain **buyer-provided**, explicitly authorized sample inputs and approved test Supabase project; map fields and evidence IDs to a dedicated test schema; add role-based review/authentication, source provenance, conflict handling, retry/rollback tests, and idempotent inserts with unique approval keys. Require manual approval before any test-database write. Validate the export-to-Supabase adapter against the buyer's sample and document rerun instructions and acceptance tests. Do not imply the offline SQLite database is Supabase. No subscriptions, ads, charge, buyer messaging, or Connect spend is authorized by this demo.

### Limits

This is an operator-run prototype, not a robust untrusted-document parser: values are supplied in a JSON fixture, not extracted by an LLM. Evidence excerpts and optional HTTPS source links are *claims to be checked*, not authoritative truth. A reviewer must inspect the actual underlying source and independently verify each proposed value. SHA-256 binds the submitted source label and excerpt (and a source URL when provided), but does not prove any of them truthful or authenticated. The tool omits concurrency controls and access-control roles, intentionally has no automatic writer to live services, and must not be marketed as production-ready.

### Optional Supabase handoff — separately authorized test project only

The new `supabase_test_handoff.py` prepares deterministic approval-key rows from the reviewed SQLite demo. Running `python supabase_test_handoff.py --db /tmp/apex-fictional-pilot.sqlite` makes **zero network requests**. It rejects changed evidence and excludes pending/rejected records. Remote POST requires a buyer-provided dedicated test project, a fixed table named `apex_evidence_pilot_test` with a unique `approval_key`, a securely supplied `APEX_SUPABASE_TEST_API_KEY`, and both `--execute-test-write` and `--confirm-dedicated-test-project`. No redirects or arbitrary endpoints are allowed. Obtain a funded contract, scope, access authorization, table schema and independent readback proof before treating HTTP acceptance as a stored record or customer delivery. No live Supabase request or buyer data was used for this PR.
