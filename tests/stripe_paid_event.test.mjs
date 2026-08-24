import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { normalizedLeadReference, paidEvent } from "../supabase/functions/stripe-revenue/paid-event.mjs";

function event(type, object) {
  return { type, data: { object } };
}

test("counts a paid one-time Checkout Session", () => {
  const payment = paidEvent(event("checkout.session.completed", {
    id: "cs_one_time",
    mode: "payment",
    payment_status: "paid",
    amount_total: 12500,
    currency: "usd",
    payment_intent: "pi_one_time",
    client_reference_id: "123e4567-e89b-42d3-a456-426614174000",
    customer_details: { email: " Buyer@Example.com " },
  }));

  assert.deepEqual(payment, {
    amount: 12500,
    currency: "USD",
    email: "buyer@example.com",
    paymentReference: "pi_one_time",
    clientReferenceId: "123e4567-e89b-42d3-a456-426614174000",
    kind: "one_time_checkout",
  });
});

test("counts a delayed one-time Checkout payment only after success", () => {
  assert.equal(paidEvent(event("checkout.session.completed", {
    id: "cs_delayed",
    mode: "payment",
    payment_status: "unpaid",
    amount_total: 12500,
    currency: "usd",
  })), null);

  assert.equal(
    paidEvent(event("checkout.session.async_payment_succeeded", {
      id: "cs_delayed",
      mode: "payment",
      payment_status: "paid",
      amount_total: 12500,
      currency: "usd",
    }))?.kind,
    "one_time_checkout",
  );
});

test("ignores subscription Checkout completion to prevent double counting", () => {
  assert.equal(paidEvent(event("checkout.session.completed", {
    id: "cs_subscription",
    mode: "subscription",
    payment_status: "paid",
    amount_total: 4900,
    currency: "usd",
    subscription: "sub_123",
  })), null);
});

test("counts the subscription invoice, including the initial invoice", () => {
  const payment = paidEvent(event("invoice.paid", {
    id: "in_123",
    subscription: "sub_123",
    amount_paid: 4900,
    currency: "usd",
    customer_email: "member@example.com",
    payment_intent: "pi_subscription",
  }));

  assert.deepEqual(payment, {
    amount: 4900,
    currency: "USD",
    email: "member@example.com",
    paymentReference: "pi_subscription",
    clientReferenceId: "",
    kind: "subscription_invoice",
  });
});

test("supports the current Invoice parent subscription shape", () => {
  const payment = paidEvent(event("invoice.paid", {
    id: "in_current",
    parent: { subscription_details: { subscription: "sub_current" } },
    payments: {
      data: [{ payment: { payment_intent: "pi_current" } }],
    },
    amount_paid: 9900,
    currency: "eur",
  }));

  assert.equal(payment?.paymentReference, "pi_current");
  assert.equal(payment?.currency, "EUR");
  assert.equal(payment?.kind, "subscription_invoice");
});

test("ignores paid invoices that are not subscription revenue", () => {
  assert.equal(paidEvent(event("invoice.paid", {
    id: "in_manual",
    amount_paid: 3000,
    currency: "usd",
  })), null);
});

test("accepts only UUID lead references", () => {
  assert.equal(
    normalizedLeadReference("123E4567-E89B-42D3-A456-426614174000"),
    "123e4567-e89b-42d3-a456-426614174000",
  );
  assert.equal(normalizedLeadReference("customer@example.com"), "");
  assert.equal(normalizedLeadReference("../../../secret"), "");
});

test("consented preview checkout carries the non-sensitive lead reference", () => {
  const offer = readFileSync(new URL("../sales/offer.html", import.meta.url), "utf8");
  assert.match(offer, /id="instant-setup-link"/);
  assert.match(offer, /url\.searchParams\.set\('client_reference_id', leadId\)/);
  assert.match(offer, /attributeCheckout\(result\.lead_id\)/);
});
