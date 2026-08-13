# Public offer page

`sales/offer.html` is a static conversion page for the approved AI Revenue Agent managed-plan experiment.

## Publish gate

Do not publish the page with active purchase buttons until the correct Stripe account for RMC Family Enterprises LLC / AI Revenue Agent is connected and the payment links have been verified.

The page accepts two HTTPS checkout URLs as query parameters:

- `setup` — $100 one-time setup checkout
- `managed` — optional $99/month managed-plan checkout

Example shape:

```text
/offer.html?setup=https%3A%2F%2F...&managed=https%3A%2F%2F...
```

The buttons remain disabled when URLs are absent. The managed plan is explicitly optional and customer-initiated.

## Consented preview-request form

The form in `offer.html` is disabled until `data-lead-endpoint` contains the verified HTTPS URL for the inbound service's `/leads` route. Configure `INBOUND_ALLOWED_ORIGINS` with the exact public offer-page origin. Keep the service bound to localhost behind an HTTPS reverse proxy; do not expose its plain HTTP port directly.

Before activation, publish a real privacy notice at `/privacy`, verify the final domain and HTTPS certificate, submit a test lead, confirm its consent audit record, and confirm that no message is automatically sent.
