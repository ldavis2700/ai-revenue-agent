-- Run only against the disposable CI PostgreSQL database, never the live ledger.
begin;
insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_a','003','stripe','checkout.session.completed','pi_one','one_time_checkout',10000,'USD',now(),'cs_one')
on conflict (processor,property_id,source_object_id) do nothing;

-- Same event retried and a distinct notification for the same purchase.
insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_a','003','stripe','checkout.session.completed','pi_one','one_time_checkout',10000,'USD',now(),'cs_one'),
       ('evt_b','003','stripe','checkout.session.async_payment_succeeded','pi_one','one_time_checkout',10000,'USD',now(),'cs_one')
on conflict (processor,property_id,source_object_id) do nothing;

-- Genuine separate invoices for recurring billing must both survive.
insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_c','003','stripe','invoice.paid','in_one','subscription_invoice',9900,'USD',now(),'in_one'),
       ('evt_d','003','stripe','invoice.paid','pi_second','subscription_invoice',9900,'USD',now(),'in_two'),
       ('evt_e','003','stripe','invoice.paid','pi_late_expansion','subscription_invoice',9900,'USD',now(),'in_one')
on conflict (processor,property_id,source_object_id) do nothing;

do $$ begin
  if (select count(*) from public.verified_revenue_events) <> 3 then
    raise exception 'Separate notifications must not become separate purchases';
  end if;
  if (select sum(amount_cents) from public.verified_revenue_events) <> 29800 then
    raise exception 'Revenue total inflated or real renewal dropped';
  end if;
  if not exists (select 1 from public.verified_revenue_events where processor_event_id='evt_a' and source_object_id='cs_one') then
    raise exception 'Original processor event audit reference was lost';
  end if;
  if has_table_privilege('anon','public.verified_revenue_events','SELECT') or
     has_table_privilege('authenticated','public.verified_revenue_events','INSERT') then
    raise exception 'Revenue ledger must remain server-only';
  end if;
end $$;
rollback;
