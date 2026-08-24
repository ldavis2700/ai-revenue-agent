create table if not exists public.verified_revenue_events (
  processor_event_id text primary key,
  property_id text not null,
  lead_id uuid references public.inbound_leads(id) on delete set null,
  processor text not null check (processor = 'stripe'),
  event_type text not null,
  payment_reference text not null,
  revenue_kind text not null check (revenue_kind in ('one_time_checkout', 'subscription_checkout', 'subscription_invoice')),
  amount_cents bigint not null check (amount_cents > 0),
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  customer_email_hash text,
  occurred_at timestamptz not null,
  created_at timestamptz not null default now()
);

alter table public.verified_revenue_events enable row level security;
revoke all on table public.verified_revenue_events from anon, authenticated;

create index if not exists verified_revenue_events_property_occurred_idx
  on public.verified_revenue_events (property_id, occurred_at desc);
