import assert from "node:assert/strict";
import test from "node:test";
import { normalizeLeadPayload, text } from "../supabase/functions/revenue-inbound/lead-intake.mjs";

test("normalizes a valid consented lead", () => {
  const result = normalizeLeadPayload({
    contact_email: "  Buyer@Example.COM  ",
    company_name: "  Buyer Co  ",
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
    contact_consent: true,
    privacy_acknowledged: true,
  });
  assert.deepEqual(result.errors, []);
});

test("requires explicit contact consent and privacy acknowledgement", () => {
  const result = normalizeLeadPayload({
    email: "owner@example.com",
    company: "Owner Co",
    contact_consent: "true",
    privacy_acknowledged: 1,
  });
  assert.deepEqual(result.errors, [
    "affirmative_contact_consent_required",
    "privacy_acknowledgement_required",
  ]);
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
