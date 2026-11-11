# Consent-first customer-inquiry demonstration (offline only)

This original demonstration is **not a deployed production service, a completed buyer contract or a revenue receipt**. It prepares a human-review queue from explicitly fictional CSV data and sends **zero** messages, incurs no AI API charges, and uses only Python's standard library. It does not alter APEX's live inbound, consent, delivery or billing systems.

## Reproduce locally

From the repository root, run:

```sh
python -m unittest discover -s tests -p 'test_consent_first_inquiry_pilot.py' -v
python scripts/consent_first_inquiry_pilot.py /path/to/fictional_inquiries.csv /path/to/new_review_output.csv
```

Required CSV columns: `inquiry_id,email,message,consent_to_reply,opted_out,status`. A draft for human review is prepared only for a **unique, safe** inquiry ID with valid email, `consent_to_reply=true`, `opted_out=false` and `status=new`. All other records are held. **Every occurrence of a repeated ID is held**, including if a later duplicate indicates an opt-out; an earlier record cannot be approved merely because it appeared first. Case-insensitive duplicate IDs are treated as ambiguous. Dangerous or malformed ID strings are never copied into the output; no user-controlled message is echoed. An existing review output is never overwritten.

This is a privacy-oriented prototype, not complete compliance, fraud prevention, a legal opinion, real identity verification, or proof that consent is current or obtained lawfully. Before customer use, verify the exact client scope, retention/deletion and audit requirements, authorized delivery system, accessibility, provider terms, original rights and asset hash, client QA/acceptance, and an approved non-Stripe collection and settlement path. Keep outbound actions behind independent consent and provider checks. Never treat tests, an invoice, or local receipt arithmetic as money received.

