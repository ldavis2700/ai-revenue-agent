import test from "node:test";
import assert from "node:assert/strict";

import { paidEvent } from "../supabase/functions/stripe-revenue/paid-event.mjs";

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
    customer_details: { email: " Buyer@Example.com " },
  }));

  assert.deepEqual(payment, {
    amount: 12500,
    currency: "USD",
    email: "buyer@example.com",
    paymentReference: "pi_one_time",
    kind: "one_time_checkout",
    sourceObjectId: "cs_one_time",
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
    kind: "subscription_invoice",
    sourceObjectId: "in_123",
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


test("different event IDs and success types share one purchase key", () => {
  const object = { id: "cs_same", mode: "payment", payment_status: "paid", amount_total: 10000 };
  const a = paidEvent({ ...event("checkout.session.completed", object), id: "evt_one" });
  const b = paidEvent({ ...event("checkout.session.async_payment_succeeded", object), id: "evt_two" });
  assert.equal(a.sourceObjectId, b.sourceObjectId);
  const c = paidEvent(event("checkout.session.completed", { ...object, id: "cs_other" }));
  assert.notEqual(a.sourceObjectId, c.sourceObjectId);
});

test("invoice key is independent of expanded or missing PaymentIntent fields", () => {
  const object = { id: "in_same", subscription: "sub_123", amount_paid: 9900 };
  assert.equal(paidEvent(event("invoice.paid", object)).sourceObjectId,
    paidEvent(event("invoice.paid", { ...object, payment_intent: "pi_new" })).sourceObjectId);
});

test("missing and malformed source IDs never become a shared empty purchase key", () => {
  for (const id of [undefined, null, "", {}, 123, "cs_", "in_wrong", "cs_has space"]) {
    assert.equal(paidEvent(event("checkout.session.completed", {
      id, mode: "payment", payment_status: "paid", amount_total: 10000,
    })), null);
  }
  assert.equal(paidEvent(event("invoice.paid", { id: "cs_wrong", subscription: "sub_1" })), null);
});
