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

The first export contains no approved records. After the operator's explicit correction, export contains only the accepted value plus its original source label and SHA-256 evidence digest. Re-ingesting changed evidence for the same ID fails closed. Repeated identical decisions are idempotent; changing a completed review requires a new evidence record. No automatic approval, production webhook, cloud transmission, email, API key, or deployment is involved.

### Buyer-scoped paid pilot handoff (not yet performed)

Only after a funded contract and written scope: obtain **buyer-provided**, explicitly authorized sample inputs and approved test Supabase project; map fields and evidence IDs to a dedicated test schema; add role-based review/authentication, source provenance, conflict handling, retry/rollback tests, and idempotent inserts with unique approval keys. Require manual approval before any test-database write. Validate the export-to-Supabase adapter against the buyer's sample and document rerun instructions and acceptance tests. Do not imply the offline SQLite database is Supabase. No subscriptions, ads, charge, buyer messaging, or Connect spend is authorized by this demo.

### Limits

This is an operator-run prototype, not a robust untrusted-document parser: values are supplied in a JSON fixture, not extracted by an LLM. Evidence excerpts are *claims to be checked*, not authoritative truth. A reviewer must inspect the actual underlying source and independently verify each proposed value. SHA-256 binds the submitted source label and excerpt, but does not prove either one is truthful or authenticated. The tool omits concurrency controls and access-control roles, intentionally has no automatic writer to live services, and must not be marketed as production-ready.
