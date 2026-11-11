const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function text(value, max = 500) {
  return String(value ?? "").trim().slice(0, max);
}

export function normalizeLeadPayload(value) {
  const payload = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const email = text(payload.contact_email ?? payload.email, 320).toLowerCase();
  const company = text(payload.company_name ?? payload.company, 200);
  const errors = [];

  if (text(payload.website_confirm, 100)) errors.push("spam_check_failed");
  if (!EMAIL_PATTERN.test(email)) errors.push("valid_contact_email_required");
  if (!company) errors.push("company_name_required");
  if (payload.contact_consent !== true) errors.push("affirmative_contact_consent_required");
  if (payload.privacy_acknowledged !== true) errors.push("privacy_acknowledgement_required");

  return { payload, email, company, errors };
}

/** Insert one new request only. A repeated request must never reset an existing
 * lead's processing status, revocation, or original consent audit record.
 * The database has a unique (property_id, email_hash) constraint.
 */
export async function insertUniqueLead(table, record) {
  return table.upsert(record, {
    onConflict: "property_id,email_hash",
    ignoreDuplicates: true,
  }).select("id").maybeSingle();
}


/** Bound actual incoming bytes rather than trusting the Content-Length header.
 * A public intake endpoint must not call request.json() on an unlimited stream.
 * This helper has no network, DB, or customer side effects.
 */
export async function readBoundedJson(request, maxBytes) {
  const lengthHeader = request.headers.get("content-length");
  if (lengthHeader !== null) {
    const declared = Number(lengthHeader);
    if (!Number.isSafeInteger(declared) || declared < 0 || declared > maxBytes) {
      return { ok: false, status: 413, error: "invalid_body_size" };
    }
  }
  if (!request.body) return { ok: false, status: 400, error: "invalid_json" };

  const reader = request.body.getReader();
  const bytes = new Uint8Array(maxBytes);
  let count = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value.byteLength > maxBytes - count) {
        await reader.cancel().catch(() => {});
        return { ok: false, status: 413, error: "invalid_body_size" };
      }
      bytes.set(value, count);
      count += value.byteLength;
    }
    const decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(0, count));
    return { ok: true, value: JSON.parse(decoded) };
  } catch {
    return { ok: false, status: 400, error: "invalid_json" };
  } finally {
    reader.releaseLock();
  }
}
