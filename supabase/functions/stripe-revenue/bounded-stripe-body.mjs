/** Read the exact UTF-8 Stripe signature payload within a hard byte limit.
 * Reject oversized chunked requests too: Content-Length is only a hint.
 * Never parse, reserialize or normalize the signed JSON before HMAC verification.
 */
export async function readBoundedStripeBody(request, maxBytes) {
  const header = request.headers.get('content-length');
  if (header !== null) {
    const declared = Number(header);
    if (!Number.isSafeInteger(declared) || declared < 0 || declared > maxBytes) {
      return { ok: false, status: 413, error: 'invalid_body_size' };
    }
  }
  if (!request.body) return { ok: false, status: 400, error: 'invalid_body' };

  const reader = request.body.getReader();
  const bytes = new Uint8Array(maxBytes);
  let count = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value.byteLength > maxBytes - count) {
        await reader.cancel().catch(() => {});
        return { ok: false, status: 413, error: 'invalid_body_size' };
      }
      bytes.set(value, count);
      count += value.byteLength;
    }
    return {
      ok: true,
      text: new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(0, count)),
    };
  } catch {
    return { ok: false, status: 400, error: 'invalid_body' };
  } finally {
    reader.releaseLock();
  }
}
