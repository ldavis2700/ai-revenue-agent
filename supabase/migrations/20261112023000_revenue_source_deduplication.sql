-- Source object IDs are stable across distinct Stripe notification IDs.
-- Preserve the original notification and PaymentIntent references for auditing.
-- Historical rows remain nullable: never fabricate a Checkout Session/invoice
-- ID from a PaymentIntent. Reconcile old rows before replaying them. The initial
-- production rollout was prepared against an empty verified revenue ledger.
alter table public.verified_revenue_events
  add column if not exists source_object_id text;

create unique index if not exists verified_revenue_events_source_object_key
  on public.verified_revenue_events (processor, property_id, source_object_id);

comment on column public.verified_revenue_events.source_object_id is
  'Stripe Checkout Session or invoice ID; stable across notification retries. Historical rows require verified reconciliation before replay.';
