# Fictional Lead Recovery Demo — no real customer data

This example supports the proposed [gated $249 pilot](../../sales/INSTANT_LEAD_RECOVERY_PILOT.md). **It is a local simulation, not a connected customer workflow or a deployed service.** It does not contact a lead, send messages, create a Stripe payment, request credentials, or write to an external provider.

Run from the repository root:

```bash
python scripts/lead_recovery_demo.py --input examples/lead_recovery/fictional_events.json
python scripts/lead_recovery_demo.py --input examples/lead_recovery/fictional_events.json --format csv
python -m unittest discover -s tests -p 'test_lead_recovery_demo.py' -v
```

The sample has three fictional events: two distinct valid inquiries and one duplicate. Expected review queue count **2**, rejection count **1**, outbound **false**. In the output, the acknowledgment is only a draft for owner approval.

The CSV is a *demonstration export*, not a live CRM integration. No processing state survives separate runs, and duplicate protection applies only within one input batch. Do not describe it as real-time, production-ready, durable/retry-safe processing or a tested customer integration. A real deployment needs a persistent dedupe store, durable retry/outbox, authorized connectors, access-control isolation, actual provider quota evidence, customer-consent/retention agreement, error observability and end-to-end deployment verification.

**Data policy:** Only invented, nonidentifying test scenarios. The basic validator rejects email-like strings and common U.S. phone patterns in the summary, but it is **not** a complete PII detector. Never insert real customer contacts, leads or data in this public repository or pass them to this simulation.

**Sale checkpoint:** No sale, revenue, customer adoption, payment entitlement, verified deployment or approval is implied by passing tests. Existing public checkout remains paused, and the original $100 offer is unchanged.
