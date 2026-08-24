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
