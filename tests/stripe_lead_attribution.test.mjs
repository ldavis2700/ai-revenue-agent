import test from "node:test";
import assert from "node:assert/strict";
import { resolveLeadId } from "../supabase/functions/stripe-revenue/lead-attribution.mjs";

function database(result) {
  const calls = [];
  const query = {
    from(table) { calls.push(["from", table]); return this; },
    select(columns) { calls.push(["select", columns]); return this; },
    eq(key, value) { calls.push([key, value]); return this; },
    async maybeSingle() { return result; },
  };
  return { query, calls };
}

test("matches the unique lead only within the payment's property and email hash", async () => {
  const { query, calls } = database({ data: { id: "lead-one" }, error: null });
  assert.equal(await resolveLeadId(query, "003", "hashed-email"), "lead-one");
  assert.deepEqual(calls, [["from", "inbound_leads"], ["select", "id"],
    ["property_id", "003"], ["email_hash", "hashed-email"]]);
});

test("a successful lookup with no matching lead leaves payment unattributed", async () => {
  const { query } = database({ data: null, error: null });
  assert.equal(await resolveLeadId(query, "003", "unmatched"), null);
});

test("missing email never queries a different or arbitrary lead", async () => {
  assert.equal(await resolveLeadId(null, "003", null), null);
});

test("database lookup failures are retriable and do not leak backend details", async () => {
  const { query } = database({ data: null, error: { message: "private database details" } });
  await assert.rejects(resolveLeadId(query, "003", "hash"), /^Error: lead_lookup_failed$/);
});
