import { createClient } from "npm:@supabase/supabase-js@2.111.0";
import { normalizeLeadPayload, text } from "./lead-intake.mjs";

const MAX_BODY_BYTES = 16 * 1024;
const PROPERTY_ID = "003";

function getSecretKey() {
  const raw = Deno.env.get("SUPABASE_SECRET_KEYS");
  return raw ? JSON.parse(raw)?.default : Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
}

function allowedOrigins() {
  return new Set(["https://ai-revenue-agent-seven.vercel.app"]);
}

function headers(origin = "") {
  const allowed = allowedOrigins();
  const cors = origin && allowed.has(origin)
    ? { "access-control-allow-origin": origin, "vary": "Origin" }
    : {};
  return {
    ...cors,
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  };
}

function json(body: unknown, status: number, origin = "") {
  return new Response(JSON.stringify(body), { status, headers: headers(origin) });
}

async function sha256(value: string) {
  const data = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("origin") ?? "";
  const allowed = allowedOrigins();

  if (!origin || !allowed.has(origin)) {
    return json({ accepted: false, errors: ["origin_not_allowed"] }, 403);
  }
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        ...headers(origin),
        "access-control-allow-methods": "POST, OPTIONS",
        "access-control-allow-headers": "content-type",
      },
    });
  }
  if (req.method !== "POST") return json({ accepted: false, errors: ["method_not_allowed"] }, 405, origin);

  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (contentLength > MAX_BODY_BYTES) return json({ accepted: false, errors: ["invalid_body_size"] }, 413, origin);

  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return json({ accepted: false, errors: ["invalid_json"] }, 400, origin);
  }

  const normalized = normalizeLeadPayload(payload);
  if (normalized.errors.length) return json({ accepted: false, errors: normalized.errors }, 422, origin);
  const { email, company } = normalized;
  const leadPayload = normalized.payload as Record<string, unknown>;

  const url = Deno.env.get("SUPABASE_URL");
  const secretKey = getSecretKey();
  if (!url || !secretKey) return json({ accepted: false, errors: ["service_not_configured"] }, 503, origin);

  const now = new Date().toISOString();
  const emailHash = await sha256(email);
  const supabase = createClient(url, secretKey, { auth: { persistSession: false } });
  const { data, error } = await supabase.from("inbound_leads").upsert({
    property_id: PROPERTY_ID,
    email,
    email_hash: emailHash,
    first_name: text(leadPayload.first_name, 100),
    company_name: company,
    industry: text(leadPayload.industry, 120),
    pain_point: text(leadPayload.pain_point, 1000),
    website: text(leadPayload.website, 500),
    source: "owned_inbound_opt_in",
    status: "new",
    contact_allowed: true,
    privacy_acknowledged: true,
    consent_version: text(leadPayload.consent_version, 100) || "contact-v1",
    consent_recorded_at: now,
    metadata: { campaign: text(leadPayload.campaign, 120) },
    updated_at: now,
  }, { onConflict: "property_id,email_hash" }).select("id").single();

  if (error) return json({ accepted: false, errors: ["database_error"] }, 500, origin);
  return json({ accepted: true, lead_id: data.id }, 202, origin);
});