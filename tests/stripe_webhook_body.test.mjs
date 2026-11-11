import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { readBoundedStripeBody } from '../supabase/functions/stripe-revenue/bounded-stripe-body.mjs';

const max = 256 * 1024;
const post = (body, headers = {}) => new Request('https://example.test/webhook', {
  method: 'POST', body, headers, ...(body instanceof ReadableStream ? { duplex: 'half' } : {}),
});

test('preserves raw Stripe signed JSON bytes and accepts exact-limit body', async () => {
  const signedJson = '{"line":"\\u0061", "spaced": true, "unicode":"é"}';
  const a = await readBoundedStripeBody(post(signedJson), max);
  assert.deepEqual(a, { ok: true, text: signedJson });
  assert.equal((await readBoundedStripeBody(post('x'.repeat(max)), max)).text.length, max);
});

test('rejects streamed oversized body with no Content-Length', async () => {
  const stream = new ReadableStream({ start(controller) {
    controller.enqueue(new Uint8Array(max));
    controller.enqueue(new Uint8Array([1]));
    controller.close();
  }});
  const req = post(stream);
  assert.equal(req.headers.has('content-length'), false);
  assert.deepEqual(await readBoundedStripeBody(req, max), {
    ok: false, status: 413, error: 'invalid_body_size',
  });
});

test('rejects declared over-limit and malformed Content-Length', async () => {
  for (const contentLength of [String(max + 1), '-1', 'NaN', '1.1']) {
    assert.deepEqual(await readBoundedStripeBody(post('{}', { 'content-length': contentLength }), max), {
      ok: false, status: 413, error: 'invalid_body_size',
    });
  }
});

test('rejects invalid UTF-8 instead of changing HMAC input bytes', async () => {
  const stream = new ReadableStream({ start(controller) {
    controller.enqueue(new Uint8Array([0xff, 0xfe]));
    controller.close();
  }});
  assert.deepEqual(await readBoundedStripeBody(post(stream), max), {
    ok: false, status: 400, error: 'invalid_body',
  });
});

test('webhook uses the bounded reader BEFORE verifying the signed event', () => {
  const source = readFileSync(new URL('../supabase/functions/stripe-revenue/index.ts', import.meta.url), 'utf8');
  const read = source.indexOf('const bounded = await readBoundedStripeBody(req, MAX_BODY_BYTES)');
  const signed = source.indexOf('const body = bounded.text;');
  const verified = source.indexOf('verifyStripeSignature(body, signature, webhookSecret)');
  assert.ok(read > 0 && signed > read && verified > signed);
  assert.equal(source.includes('await req.text()'), false);
});
