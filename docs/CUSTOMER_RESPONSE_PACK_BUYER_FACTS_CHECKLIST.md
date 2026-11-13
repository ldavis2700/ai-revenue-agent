# Customer-response pack: buyer facts and scope checklist

**Free preparation aid, not a contract, invoice, order or uploaded customer form.** This checklist helps a small cleaning or home-service business decide whether the existing **$100 one-time, human-reviewed response pack** is suitable. No payment, subscription, automatic messaging or customer-data transfer is created by reading it. The optional **$99/month support** is separately offered and requires affirmative agreement.

The actual pack contains **14 owner-reviewed draft replies**, a response-use guide, a blank inquiry tracker and **one consolidated revision**. It is a drafting deliverable, **not** a working CRM, chatbot, appointment booking integration or guaranteed extra sales. The business must check drafts before choosing to send them.

## 1. Business-approved facts (required before tailoring)

Confirm these five facts privately with the actual business owner or authorized representative. They map exactly to the five fields required by the existing offline builder `scripts/build_response_pack.py`:

| Field | What the business confirms | Hold the draft if… |
| --- | --- | --- |
| `company` | Exact business name that may appear in draft replies | Its public/operating name is uncertain |
| `services` | Cleaning or home services **actually provided**, including relevant exclusions | Service availability or coverage is unverified |
| `service_area` | Accurate general geographic service area, without customer street addresses | A specific neighborhood or city has not been confirmed |
| `quote_process` | What staff actually need to review before a quote and **who approves pricing** | Anyone wants an invented estimate, discount or availability promise |
| `escalation_contact` | The internal business role/contact authorized to resolve unusual or sensitive questions | There is no named accountable human review path |

Use clear, single-line business facts only (maximum 300 characters per field in the builder). **Do not paste customer names, private customer messages, home addresses, door/access codes, phone numbers, credentials, invoices or payment information into any field.** A buyer-specific profile and resulting pack must remain **private outside GitHub** and be shared only with the permitted buyer/delivery channel.

A local, fictional illustration of the builder's five required keys (not a verified business) is:

```json
{
  "company": "Example Cleaning Co. (fictional)",
  "services": "Hypothetical routine residential and move-out cleaning",
  "service_area": "Example County (fictional)",
  "quote_process": "Owner reviews requested scope and confirms any price privately",
  "escalation_contact": "Example company's designated human manager (fictional)"
}
```

These invented values are for an offline demonstration only. Never represent that demonstration as a real buyer profile, paid deliverable or a customer's results.

## 2. Confirm what **not** to promise

Before work begins, the business should separately confirm whether its actual policies support any draft referring to service inclusions, same-day response, callback time, discounts, availability, appointment acceptance, refunds, insurance, complaints or review requests. **Unknown means hold for human review**, not guess.

Follow-up messages are only for genuine existing inquiries with applicable permission and no opt-out. Review requests must invite candid feedback, not rewards or selective solicitation. Nothing in a draft authorizes unsolicited outreach, bulk customer messaging, or access to a buyer's inbox.

## 3. Agree on the paid pilot **before** creating a customer deliverable

A real buyer and provider-authorized operator must separately establish and privately record:

- The exact buyer, authorized contact and **consented** communication/delivery destination
- The **$100 one-time** scope: 14 tailored drafts across seven inquiry situations (two options each), use guide, blank tracker and one consolidated revision
- Which business facts the buyer has approved, the buyer's reviewer, and **an agreed delivery deadline** (never presume one)
- What counts as an acceptable draft, how to request the included revision, and any separately agreed support/refund terms
- The permitted payment rail and its actual fees; a Payment Link or draft invoice is **not** receipt or settlement
- Whether optional **$99/month** support is declined or affirmatively accepted in a **separate** agreement; no automatic enrollment

The current public APEX site is **inquiry only** and its checkout is paused. Do not charge, publish customer details, enable autonomous delivery or treat a free preview inquiry as a contract. First verify the genuine scope and payment/refund/dispute state through the authorized provider.

## 4. Deliver, check and account for **real** work

For an agreed, paid pilot, the operator checks all 14 messages against approved facts, uses the offline pack builder, privately verifies the actual files and SHA-256 manifest, and has a qualified human review the wording. Deliver only through a provider-authorized channel to the verified buyer destination. Preserve a genuine delivery receipt and timestamp, then record the buyer's actual acceptance or revision request. Do not mark prepared files as delivered.

Separately account for gross payment, processor/platform fees, refund/dispute amounts, delivery/revision/support labor, existing infrastructure allocation, acquisition opportunity costs, net collected contribution and eventual owner distributions. **Unknown costs stay unknown; receipts, invoices, page views and hosted tests are not owner take-home.**

## 5. A genuine business can request the free preview

Use the [existing APEX opt-in inquiry page](https://apex-content-worker-production.up.railway.app/?utm_source=github&utm_medium=buyer_facts_guide&utm_campaign=apex_pilot_20261113#lead-form) to describe **only the type of customer-response problem**. Its immediate response examples are generic, not tailored to the submitted problem. A tailored preview requires separate human review and permitted follow-up; no checkout is available from that request.

For a worked **fictional** sample of the full deliverable, use the [14-response demonstration](FICTIONAL_14_RESPONSE_PACK_DEMONSTRATION.md). To organize owner-reviewed replies privately, use the [free blank tracker](FREE_CUSTOMER_INQUIRY_TRACKER_GUIDE.md). None is proof of a paying customer.
