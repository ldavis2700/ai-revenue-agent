-- Keep verified payment-to-lead attribution joins efficient as revenue volume grows.
create index if not exists verified_revenue_events_lead_id_idx
  on public.verified_revenue_events (lead_id);
