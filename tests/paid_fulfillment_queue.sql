-- Disposable CI PostgreSQL only. No synthetic records belong in production.
begin;
-- Supabase's service role has these existing ledger privileges. Exercise the
-- trigger as that role rather than relying only on PostgreSQL superuser access.
grant usage on schema public to service_role;
grant select, insert on public.verified_revenue_events to service_role;
set local role service_role;
insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_setup','003','stripe','checkout.session.completed','pi_setup','one_time_checkout',10000,'USD',now(),'cs_setup'),
       ('evt_month','003','stripe','invoice.paid','in_month','subscription_invoice',9900,'USD',now(),'in_month'),
       ('evt_foreign','002','stripe','checkout.session.completed','pi_foreign','one_time_checkout',10000,'USD',now(),'cs_foreign');

-- Different notifications for the same purchase must not generate more work.
insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_duplicate','003','stripe','checkout.session.async_payment_succeeded','pi_setup','one_time_checkout',10000,'USD',now(),'cs_setup')
on conflict (processor,property_id,source_object_id) do nothing;
reset role;

do $$ begin
  if (select count(*) from public.paid_fulfillment_queue) <> 2 then
    raise exception 'Queue lost paid work, duplicated it, or admitted another property';
  end if;
  if not exists (select 1 from public.paid_fulfillment_queue where processor_event_id='evt_setup' and work_kind='setup' and status='pending') then
    raise exception 'Unmatched setup payment must still create an obligation';
  end if;
  if not exists (select 1 from public.paid_fulfillment_queue where processor_event_id='evt_month' and work_kind='managed_cycle') then
    raise exception 'Subscription renewal must create separate managed work';
  end if;
  begin
    update public.paid_fulfillment_queue set status='delivered' where processor_event_id='evt_setup';
    raise exception 'Delivery without evidence was allowed';
  exception when check_violation then null; end;
  begin
    update public.paid_fulfillment_queue set status='blocked' where processor_event_id='evt_setup';
    raise exception 'Silent blocked work was allowed';
  exception when check_violation then null; end;
  begin
    insert into public.paid_fulfillment_queue (processor_event_id,work_kind) values ('unpaid','setup');
    raise exception 'Unpaid work entered payment queue';
  exception when foreign_key_violation then null; end;
  if has_table_privilege('anon','public.paid_fulfillment_queue','SELECT') or
     has_table_privilege('authenticated','public.paid_fulfillment_queue','INSERT') or
     has_function_privilege('anon','public.enqueue_verified_apex_work()','EXECUTE') then
    raise exception 'Public access to fulfillment obligations';
  end if;
end $$;

update public.paid_fulfillment_queue
set status='delivered', artifact_sha256=repeat('a',64),
    delivery_evidence_url='https://example.test/receipt', delivered_at=now()
where processor_event_id='evt_setup';

-- Prove trigger failures roll back the receipt instead of silently losing work.
alter table public.paid_fulfillment_queue add constraint reject_test_work
  check (processor_event_id <> 'evt_atomic');
do $$ begin
  begin
    insert into public.verified_revenue_events
      (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
    values ('evt_atomic','003','stripe','checkout.session.completed','pi_atomic','one_time_checkout',10000,'USD',now(),'cs_atomic');
    raise exception 'Expected queue failure';
  exception when check_violation then null; end;
  if exists (select 1 from public.verified_revenue_events where processor_event_id='evt_atomic') then
    raise exception 'Receipt committed without its work obligation';
  end if;
end $$;
rollback;
