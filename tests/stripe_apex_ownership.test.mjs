import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isApexRevenueEvent } from '../supabase/functions/stripe-revenue/apex-ownership.mjs';

const e = (type, object, livemode = true) => ({ type, livemode, data: { object } });
const setup = 'plink_1U41IsPBIDRbWEMWwWHrFyko';
const other = 'plink_1U3RuIPBIDRbWEMWMClTP4aK';
const managed = { apex_property_id: '003', apex_offer: 'ai_response_managed_monthly' };

test('accepts only the verified APEX setup link in live paid Checkout sessions', () => {
  assert.equal(isApexRevenueEvent(e('checkout.session.completed', {
    mode: 'payment', payment_link: setup, payment_status: 'paid',
  })), true);
  assert.equal(isApexRevenueEvent(e('checkout.session.async_payment_succeeded', {
    mode: 'payment', payment_link: setup, payment_status: 'paid',
  })), true);
});

test('rejects HAEVEN Payment Links even if session metadata claims APEX', () => {
  assert.equal(isApexRevenueEvent(e('checkout.session.completed', {
    mode: 'payment', payment_link: other, metadata: { apex_property_id: '003' },
  })), false);
});

test('rejects an arbitrary link and sessions with missing link provenance', () => {
  assert.equal(isApexRevenueEvent(e('checkout.session.completed', {
    mode: 'payment', payment_link: 'plink_other',
  })), false);
  assert.equal(isApexRevenueEvent(e('checkout.session.completed', {
    mode: 'payment',
  })), false);
});

test('does not attribute subscription Checkout and double-count the invoice', () => {
  assert.equal(isApexRevenueEvent(e('checkout.session.completed', {
    mode: 'subscription', payment_link: 'plink_1U41J2PBIDRbWEMW8Eniz2mW',
  })), false);
});

test('accepts APEX managed invoice with current subscription snapshot', () => {
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    parent: { subscription_details: { subscription: 'sub_a', metadata: managed } },
  })), true);
});

test('accepts APEX managed invoice with legacy subscription snapshot', () => {
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    subscription_details: { metadata: managed }, subscription: 'sub_a',
  })), true);
});

test('rejects HAEVEN subscription invoices', () => {
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    parent: {
      subscription_details: {
        metadata: { apex_property_id: '002', apex_offer: 'haeven_premium_monthly' },
      },
    },
  })), false);
});

test('rejects invoice with missing, incomplete or inconsistent metadata', () => {
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    subscription: 'sub_a',
  })), false);
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    subscription_details: { metadata: { apex_property_id: '003' } },
  })), false);
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    subscription_details: {
      metadata: { apex_property_id: '003', apex_offer: 'other' },
    },
  })), false);
});

test('rejects test-mode and unrelated events', () => {
  assert.equal(isApexRevenueEvent(e('invoice.paid', {
    subscription_details: { metadata: managed },
  }, false)), false);
  assert.equal(isApexRevenueEvent(e('charge.refunded', {
    metadata: managed,
  })), false);
  assert.equal(isApexRevenueEvent({
    type: 'checkout.session.completed', livemode: true,
  }), false);
  assert.equal(isApexRevenueEvent(null), false);
});

// Guard the integration boundary: a tested helper alone must never be
// confused with a webhook that actually calls it before any receipt insert.
test('source webhook gates ownership before normalizing or storing revenue', () => {
  const source = readFileSync(new URL('../supabase/functions/stripe-revenue/index.ts', import.meta.url), 'utf8');
  const guard = source.indexOf('if (!isApexRevenueEvent(event))');
  const normalize = source.indexOf('const payment = paidEvent(event);');
  const insert = source.indexOf('from("verified_revenue_events")');
  assert.ok(guard > 0 && normalize > guard && insert > normalize);
});
