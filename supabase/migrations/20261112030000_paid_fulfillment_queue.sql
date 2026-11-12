-- Transactional outbox: a verified receipt and its work obligation commit
-- together. A database error prevents webhook acknowledgement so Stripe retries.
create table public.paid_fulfillment_queue (
  processor_event_id text primary key
    references public.verified_revenue_events(processor_event_id) on delete restrict,
  work_kind text not null check (work_kind in ('setup', 'managed_cycle')),
  status text not null default 'pending'
    check (status in ('pending', 'blocked', 'delivered')),
  blocker text,
  artifact_sha256 text,
  delivery_evidence_url text,
  delivered_at timestamptz,
  created_at timestamptz not null default now(),
  constraint delivered_requires_evidence check (
    status <> 'delivered' or (
      artifact_sha256 is not null and artifact_sha256 ~ '^[0-9a-f]{64}$'
      and delivery_evidence_url is not null
      and delivery_evidence_url ~ '^https://[^/@[:space:]]+(/[^[:space:]]*)?$'
      and delivered_at is not null and delivered_at >= created_at
    )
  ),
  constraint blocked_requires_reason check (
    status <> 'blocked' or (blocker is not null and length(trim(blocker)) > 0)
  )
);

alter table public.paid_fulfillment_queue enable row level security;
revoke all on public.paid_fulfillment_queue from public, anon, authenticated;
grant select, insert, update on public.paid_fulfillment_queue to service_role;
create index paid_fulfillment_queue_pending_idx
  on public.paid_fulfillment_queue (created_at) where status <> 'delivered';

create function public.enqueue_verified_apex_work()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if new.property_id = '003' and new.processor = 'stripe'
     and new.revenue_kind in ('one_time_checkout', 'subscription_invoice') then
    insert into public.paid_fulfillment_queue (processor_event_id, work_kind)
    values (new.processor_event_id,
      case when new.revenue_kind = 'one_time_checkout' then 'setup' else 'managed_cycle' end)
    on conflict (processor_event_id) do nothing;
  end if;
  return new;
end;
$$;
revoke all on function public.enqueue_verified_apex_work() from public, anon, authenticated;
grant execute on function public.enqueue_verified_apex_work() to service_role;

create trigger verified_apex_payment_enqueues_work
  after insert on public.verified_revenue_events
  for each row execute function public.enqueue_verified_apex_work();

-- Recover any receipts predating this trigger; no charge or delivery is created.
insert into public.paid_fulfillment_queue (processor_event_id, work_kind)
select processor_event_id,
  case when revenue_kind = 'one_time_checkout' then 'setup' else 'managed_cycle' end
from public.verified_revenue_events
where property_id = '003' and processor = 'stripe'
  and revenue_kind in ('one_time_checkout', 'subscription_invoice')
on conflict (processor_event_id) do nothing;

comment on table public.paid_fulfillment_queue is
  'Server-only paid work obligations. Pending is not permission to send, proof of buyer identity, or completed delivery. Evidence fields validate shape only; operators must verify the actual artifact and delivery receipt.';
