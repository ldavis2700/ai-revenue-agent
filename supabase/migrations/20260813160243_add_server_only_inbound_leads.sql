create table if not exists public.inbound_leads (
  id uuid primary key default gen_random_uuid(),
  property_id text not null references public.properties(id),
  email text not null,
  email_hash text not null,
  first_name text not null default '',
  company_name text not null,
  industry text not null default '',
  pain_point text not null default '',
  website text not null default '',
  source text not null default 'owned_inbound_opt_in',
  status text not null default 'new' check (status in ('new','qualified','contacted','suppressed','won','closed_lost')),
  contact_allowed boolean not null default false,
  privacy_acknowledged boolean not null default false,
  consent_version text not null,
  consent_recorded_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (property_id, email_hash)
);

alter table public.inbound_leads enable row level security;
revoke all on table public.inbound_leads from anon, authenticated, public;
grant select, insert, update on table public.inbound_leads to service_role;

create index if not exists inbound_leads_property_status_idx
  on public.inbound_leads (property_id, status, created_at desc);

comment on table public.inbound_leads is
  'Server-only consented inbound prospects for AI Revenue Agent property 003; no anonymous Data API access.';
