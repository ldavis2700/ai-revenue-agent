/** A transient lookup error must cause a webhook retry, not a permanent orphan. */
export async function resolveLeadId(supabase, propertyId, emailHash) {
  if (!emailHash) return null;
  const { data, error } = await supabase.from("inbound_leads")
    .select("id").eq("property_id", propertyId).eq("email_hash", emailHash).maybeSingle();
  if (error) throw new Error("lead_lookup_failed");
  return data?.id ?? null;
}
