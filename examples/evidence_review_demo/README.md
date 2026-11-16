# Evidence → review → structured record: synthetic buyer-workflow proof

**Offline, source-only demonstration.** This is a deliberately small, original workflow
sample for assessing AI research / evidence-extraction buyer requests. It is not a
client engagement, a working Supabase integration, an AI model, or a deployed service.
All sample data is synthetic. It needs no credentials, network access, payments or
client documents.

## Run (Python 3.10+)

```bash
cd examples/evidence_review_demo
python evidence_review_demo.py --decision approve
python evidence_review_demo.py --decision correct --corrected-value '245 USD'
python evidence_review_demo.py --decision reject
python -m unittest -v test_evidence_review_demo.py
```

Demonstrated: a proposed structured value must carry an **exact source quote**;
a human approves, corrects, or rejects it; only approved/corrected records are
inserted into a local SQLite table, preserving source references, quoted evidence,
and the original proposed value. SQL insertions are parameterized. Rejections
perform no write.

**Not demonstrated:** LLM extraction, a UI, authentication, actual Supabase access,
client data handling, idempotency across external systems, real production security,
or any paid customer delivery.

## Acceptance before a paid pilot

1. Confirm the buyer's exact sample and permitted data-handling boundaries, plus a
   separately funded agreement and authorized access.
2. Implement a least-privilege review UI and a dedicated *test* Supabase schema
   with appropriate row-level policies; never use credentials in code or logs.
3. Verify persistence of the evidence link and review decision, rejected-record
   exclusion, retry safety, rollback, and isolation of customer documents.
4. Quote separate fees, build scope and timeline only after evidence and integration
   requirements are understood. Do not claim prior client results from this sample.

This PR must not deploy, enable checkout, trigger outreach, spend Upwork Connects,
or override any owner approval / privacy / contract gates.
