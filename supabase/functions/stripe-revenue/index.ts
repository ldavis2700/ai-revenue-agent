import { createClient } from "npm:@supabase/supabase-js@2.111.0";
import { paidEvent } from "./paid-event.mjs";

const PROPERTY_ID = "003";
const MAX_BODY_BYTES = 256 * 1024;
const SIGNATURE_TOLERANCE_SECONDS = 300;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function secretKey() {
  const raw = Deno.env.get("SUPABASE_SECRET_KEYS");
  return raw ? JSON.parse(raw)?.default : Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
}

function parseStripeSignature(value: string) {
  const fields = value.split(",").map((field) => field.split("=", 2));
  return {
    timestamp: Number(fields.find(([key]) => key === "t")?.[1] ?? 0),
    signatures: fields.filter(([key]) => key === "v1").map(([, signature]) => signature),
  };
}

function constantTimeEqual(left: string, right: string) {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let index = 0; index < left.length; index++) mismatch |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return mismatch === 0;
}

async function hmacHex(secret: string, payload: string) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return [...new Uint8Array(signature)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function verifyStripeSignature(body: string, header: string, secret: string) {
  const { timestamp, signatures } = parseStripeSignature(header);
  if (!timestamp || !signatures.length) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - timestamp) > SIGNATURE_TOLERANCE_SECONDS) return false;
  const expected = await hmacHex(secret, `${timestamp}.${body}`);
  return signatures.some((signature) => constantTimeEqual(signature, expected));
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ received: false, error: "method_not_allowed" }, 405);
  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (contentLength > MAX_BODY_BYTES) return json({ received: false, error: "invalid_body_size" }, 413);

  const webhookSecret = Deno.env.get("STRIPE_REVENUE_WEBHOOK_SECRET") ?? "";
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const key = secretKey() ?? "";
  if (!webhookSecret || !url || !key) return json({ received: false, error: "service_not_configured" }, 503);

  const body = await req.text();
  const signature = req.headers.get("stripe-signature") ?? "";
  if (!(await verifyStripeSignature(body, signature, webhookSecret))) {
    return json({ received: false, error: "invalid_signature" }, 400);
  }

  let event: Record<string, any>;
  try {
    event = JSON.parse(body);
  } catch {
    return json({ received: false, error: "invalid_json" }, 400);
  }

  if (event.livemode !== true) {
    return json({ received: true, ignored: true, reason: "non_live_event" });
  }

  const payment = paidEvent(event);
  if (!payment) return json({ received: true, ignored: true });
  if (!Number.isInteger(payment.amount) || payment.amount <= 0) {
    return json({ received: false, error: "invalid_paid_amount" }, 422);
  }

  const supabase = createClient(url, key, { auth: { persistSession: false } });
  const emailHash = payment.email ? await sha256(payment.email) : null;
  let leadId: string | null = null;

  if (payment.clientReferenceId) {
    const { data } = await supabase.from("inbound_leads")
      .select("id")
      .eq("property_id", PROPERTY_ID)
      .eq("id", payment.clientReferenceId)
      .maybeSingle();
    leadId = data?.id ?? null;
  }

  if (!leadId && emailHash) {
    const { data } = await supabase.from("inbound_leads")
      .select("id")
      .eq("property_id", PROPERTY_ID)
      .eq("email_hash", emailHash)
      .maybeSingle();
    leadId = data?.id ?? null;
  }

  const { error } = await supabase.from("verified_revenue_events").upsert({
    processor_event_id: String(event.id),
    property_id: PROPERTY_ID,
    lead_id: leadId,
    processor: "stripe",
    event_type: String(event.type),
    payment_reference: payment.paymentReference,
    revenue_kind: payment.kind,
    amount_cents: payment.amount,
    currency: payment.currency,
    customer_email_hash: emailHash,
    occurred_at: new Date(Number(event.created ?? 0) * 1000).toISOString(),
  }, { onConflict: "processor_event_id", ignoreDuplicates: true });

  if (error) return json({ received: false, error: "database_error" }, 500);
  return json({ received: true });
});
