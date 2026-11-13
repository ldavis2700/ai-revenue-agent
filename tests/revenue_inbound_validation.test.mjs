import assert from "node:assert/strict";
import test from "node:test";
import { normalizeLeadPayload, text, insertUniqueLead, readBoundedJson, isAllowedLeadOrigin } from "../supabase/functions/revenue-inbound/lead-intake.mjs";

test("permits only the exact owned offer origins", () => {
  assert.equal(isAllowedLeadOrigin("https://ai-revenue-agent-seven.vercel.app"), true);
  assert.equal(isAllowedLeadOrigin("https://apex-content-worker-production.up.railway.app"), true);
  for (const origin of ["", null, "null", "https://evil.example", "http://apex-content-worker-production.up.railway.app",
    "https://apex-content-worker-production.up.railway.app.evil.example",
    "https://apex-content-worker-production.up.railway.app/", "https://other.up.railway.app"]) {
    assert.equal(isAllowedLeadOrigin(origin), false);
  }
});

test("normalizes a valid consented lead", () => {
  const result = normalizeLeadPayload({
    contact_email: "  Buyer@Example.COM  ",
    company_name: "  Buyer Co  ",
    pain_point: "  We need clearer responses to new inquiries.  ",
    contact_consent: true,
    privacy_acknowledged: true,
  });
  assert.deepEqual(result.errors, []);
  assert.equal(result.email, "buyer@example.com");
  assert.equal(result.company, "Buyer Co");
});

test("supports legacy email and company aliases", () => {
  const result = normalizeLeadPayload({
    email: "owner@example.com",
    company: "Owner Co",
    pain_point: "We need help responding to appointment inquiries.",
    contact_consent: true,
    privacy_acknowledged: true,
  });
  assert.deepEqual(result.errors, []);
});

test("requires explicit contact consent and privacy acknowledgement", () => {
  const result = normalizeLeadPayload({
    email: "owner@example.com",
    company: "Owner Co",
    pain_point: "Help us respond to new buyers faster.",
    contact_consent: "true",
    privacy_acknowledged: 1,
  });
  assert.deepEqual(result.errors, [
    "affirmative_contact_consent_required",
    "privacy_acknowledgement_required",
  ]);
});

test("requires meaningful preview context at the API boundary", () => {
  const base = {
    contact_email: "buyer@example.com",
    company_name: "Buyer Co",
    contact_consent: true,
    privacy_acknowledged: true,
  };
  const code = "problem_description_12_to_1000_characters_required";
  for (const pain_point of [undefined, "", "            ", "short", 123, {}, "x".repeat(1001)]) {
    const result = normalizeLeadPayload({ ...base, pain_point });
    assert.ok(result.errors.includes(code), String(pain_point));
  }
  for (const pain_point of ["x".repeat(12), "x".repeat(1000), "  Need help replying to buyers.  "]) {
    assert.deepEqual(normalizeLeadPayload({ ...base, pain_point }).errors, []);
  }
});

test("rejects the honeypot and malformed email addresses", () => {
  for (const email of ["missing-at.example.com", "name@localhost", "two words@example.com"]) {
    const result = normalizeLeadPayload({
      email,
      company: "Example Co",
      website_confirm: "spam",
      contact_consent: true,
      privacy_acknowledged: true,
    });
    assert.ok(result.errors.includes("spam_check_failed"));
    assert.ok(result.errors.includes("valid_contact_email_required"));
  }
});

test("handles non-object JSON bodies without throwing", () => {
  for (const value of [null, [], "lead"]) {
    const result = normalizeLeadPayload(value);
    assert.ok(result.errors.includes("valid_contact_email_required"));
    assert.ok(result.errors.includes("company_name_required"));
  }
});

test("trims and bounds stored text", () => {
  assert.equal(text("  abc  ", 10), "abc");
  assert.equal(text("123456", 4), "1234");
});

// Fake table simulates the existing unique (property_id,email_hash) constraint.
// No customer records are read or written by this test.
test("duplicate request preserves a revoked consent and processed status", async () => {
  const original = { id: "existing", status: "opted_out", contact_allowed: false, pain_point: "old" };
  let persisted = { ...original };
  let options, selected;
  const fakeTable = {
    upsert(record, opts) {
      options = opts;
      return { select(column) {
        selected = column;
        return { async maybeSingle() {
          if (persisted && opts.ignoreDuplicates) return { data: null, error: null };
          persisted = { id: "new", ...record };
          return { data: { id: persisted.id }, error: null };
        }};
      }};
    },
  };
  const result = await insertUniqueLead(fakeTable, {
    property_id: "003", email_hash: "hash", status: "new", contact_allowed: true, pain_point: "new",
  });
  assert.deepEqual(options, { onConflict: "property_id,email_hash", ignoreDuplicates: true });
  assert.equal(selected, "id");
  assert.deepEqual(result, { data: null, error: null });
  assert.deepEqual(persisted, original);
});

test("first valid request still inserts and returns its new receipt", async () => {
  let saved = null;
  const fakeTable = {
    upsert(record, opts) {
      return { select() { return { async maybeSingle() {
        assert.equal(opts.ignoreDuplicates, true);
        saved = { id: "new", ...record };
        return { data: { id: saved.id }, error: null };
      }}; }};
    },
  };
  const result = await insertUniqueLead(fakeTable, {
    property_id: "003", email_hash: "newhash", status: "new", contact_allowed: true,
  });
  assert.equal(result.data.id, "new");
  assert.equal(saved.status, "new");
  assert.equal(saved.contact_allowed, true);
});


test("public intake accepts well-formed JSON and an exact-size body", async () => {
  const max = 16 * 1024;
  const body = JSON.stringify({ x: "a".repeat(max - 8) });
  assert.equal(Buffer.byteLength(body), max);
  const req = new Request("https://example.test/", { method: "POST", body });
  const parsed = await readBoundedJson(req, max);
  assert.equal(parsed.ok, true);
  assert.equal(parsed.value.x.length, max - 8);
});

test("public intake rejects oversized stream even with no Content-Length", async () => {
  const max = 16 * 1024;
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(JSON.stringify({ x: "x".repeat(max) })));
      controller.close();
    },
  });
  const req = new Request("https://example.test/", { method: "POST", body: stream, duplex: "half" });
  assert.equal(req.headers.has("content-length"), false);
  assert.deepEqual(await readBoundedJson(req, max), {
    ok: false, status: 413, error: "invalid_body_size",
  });
});

test("public intake rejects oversized declared length without parsing", async () => {
  const max = 16 * 1024;
  const req = new Request("https://example.test/", {
    method: "POST", body: "{}", headers: { "content-length": String(max + 1) },
  });
  assert.deepEqual(await readBoundedJson(req, max), {
    ok: false, status: 413, error: "invalid_body_size",
  });
});

test("public intake rejects malformed JSON and invalid UTF-8", async () => {
  const max = 16 * 1024;
  const badJson = new Request("https://example.test/", { method: "POST", body: "{oops" });
  assert.deepEqual(await readBoundedJson(badJson, max), {
    ok: false, status: 400, error: "invalid_json",
  });
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array([255, 254]));
      controller.close();
    },
  });
  const invalidUtf8 = new Request("https://example.test/", { method: "POST", body: stream, duplex: "half" });
  assert.deepEqual(await readBoundedJson(invalidUtf8, max), {
    ok: false, status: 400, error: "invalid_json",
  });
});
