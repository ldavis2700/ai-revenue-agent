import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac, webcrypto } from 'node:crypto';
import { createStripeRevenueHandler } from '../supabase/functions/stripe-revenue/handler.mjs';

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const secret = 'fictional-signing-secret-for-offline-tests';
const env = { get: (name) => ({ STRIPE_REVENUE_WEBHOOK_SECRET: secret,
  SUPABASE_URL: 'https://isolated.example.test', SUPABASE_SERVICE_ROLE_KEY: 'fictional-key' })[name] };

function harness() {
  const rows = new Map();
  let clientCalls = 0;
  const handler = createStripeRevenueHandler(() => {
    clientCalls++;
    return { from: (name) => {
      if (name === 'inbound_leads') {
        const query = { select: () => query, eq: () => query,
          maybeSingle: async () => ({ data: null }) };
        return query;
      }
      assert.equal(name, 'verified_revenue_events');
      return { upsert: async (row, options) => {
        assert.deepEqual(options, { onConflict: 'processor_event_id', ignoreDuplicates: true });
        if (!rows.has(row.processor_event_id)) rows.set(row.processor_event_id, row);
        return { error: null };
      } };
    } };
  }, env);
  return { handler, rows, clientCalls: () => clientCalls };
}

function event(type, object, overrides = {}) {
  return { id: 'evt_fixture', livemode: true, created: Math.floor(Date.now() / 1000),
    type, data: { object }, ...overrides };
}

function checkout(property = '003', overrides = {}) {
  return { id: 'cs_fixture', mode: 'payment', payment_status: 'paid', amount_total: 10000,
    currency: 'usd', payment_intent: 'pi_fixture', metadata: { apex_property_id: property },
    customer_details: { email: 'fictional@example.test' }, ...overrides };
}

function signedRequest(value, timestamp = Math.floor(Date.now() / 1000)) {
  const body = JSON.stringify(value);
  const signature = createHmac('sha256', secret).update(`${timestamp}.${body}`).digest('hex');
  return new Request('https://local.example.test/webhook', { method: 'POST', body,
    headers: { 'stripe-signature': `t=${timestamp},v1=${signature}` } });
}

test('actual handler rejects missing and stale signatures before database access', async () => {
  const h = harness();
  const unsigned = new Request('https://local.example.test', { method: 'POST', body: '{}' });
  assert.equal((await h.handler(unsigned)).status, 400);
  assert.equal((await h.handler(signedRequest(event('invoice.paid', {}), 1))).status, 400);
  assert.equal(h.clientCalls(), 0);
});

test('actual handler rejects unsupported methods and missing configuration', async () => {
  const h = harness();
  assert.equal((await h.handler(new Request('https://local.example.test'))).status, 405);
  const disabled = createStripeRevenueHandler(() => assert.fail('no database'), { get: () => undefined });
  assert.equal((await disabled(signedRequest(event('invoice.paid', {})))).status, 503);
});

test('valid signatures do not turn other-app, untagged, or test payments into APEX income', async () => {
  const h = harness();
  const cases = [event('checkout.session.completed', checkout('002')),
    event('checkout.session.completed', checkout(undefined, { metadata: {} })),
    event('checkout.session.completed', checkout(), { livemode: false })];
  for (const value of cases) {
    const response = await h.handler(signedRequest(value));
    assert.equal(response.status, 200);
    assert.equal((await response.json()).ignored, true);
  }
  assert.equal(h.clientCalls(), 0);
  assert.equal(h.rows.size, 0);
});

test('signed APEX checkout persists a hashed email and duplicate deliveries use the event conflict key', async () => {
  const h = harness();
  const value = event('checkout.session.completed', checkout());
  assert.equal((await h.handler(signedRequest(value))).status, 200);
  assert.equal((await h.handler(signedRequest(value))).status, 200);
  assert.equal(h.rows.size, 1);
  const row = [...h.rows.values()][0];
  assert.equal(row.property_id, '003');
  assert.equal(row.amount_cents, 10000);
  assert.match(row.customer_email_hash, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(row).includes('fictional@example.test'), false);
});

test('subscription initial Checkout plus invoice produces only one gross-revenue entry', async () => {
  const h = harness();
  const initial = event('checkout.session.completed', checkout('003', { mode: 'subscription' }), { id: 'evt_checkout' });
  const invoice = event('invoice.paid', { id: 'in_fixture', amount_paid: 9900, currency: 'usd',
    parent: { subscription_details: { subscription: 'sub_fixture', metadata: { apex_property_id: '003' } } } }, { id: 'evt_invoice' });
  await h.handler(signedRequest(initial));
  assert.equal(h.rows.size, 0);
  await h.handler(signedRequest(invoice));
  assert.equal(h.rows.size, 1);
  assert.equal([...h.rows.values()][0].revenue_kind, 'subscription_invoice');
});

test('delayed payments are recorded only after signed async success', async () => {
  const h = harness();
  await h.handler(signedRequest(event('checkout.session.completed', checkout('003', { payment_status: 'unpaid' }))));
  assert.equal(h.rows.size, 0);
  await h.handler(signedRequest(event('checkout.session.async_payment_succeeded', checkout(), { id: 'evt_async' })));
  assert.equal(h.rows.size, 1);
});

test('invalid positive-payment amount cannot reach the database', async () => {
  const h = harness();
  const response = await h.handler(signedRequest(event('checkout.session.completed', checkout('003', { amount_total: -100 }))));
  assert.equal(response.status, 422);
  assert.equal(h.clientCalls(), 0);
});
