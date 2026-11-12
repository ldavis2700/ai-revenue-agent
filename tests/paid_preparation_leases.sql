-- Disposable CI database only; all fixtures roll back.
begin;
grant usage on schema public to service_role;
grant select, insert on public.verified_revenue_events to service_role;
set local role service_role;
insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_prep','003','stripe','checkout.session.completed','pi_prep','one_time_checkout',10000,'USD',now(),'cs_prep');

do $$
declare first_claim public.paid_fulfillment_queue;
        recovered public.paid_fulfillment_queue;
begin
  select * into first_claim from public.claim_paid_preparation('worker-a',60);
  if first_claim.processor_event_id is distinct from 'evt_prep' or first_claim.preparation_attempts <> 1 then
    raise exception 'Lost first paid obligation';
  end if;
  if exists(select 1 from public.claim_paid_preparation('worker-b')) then
    raise exception 'Active work was claimed twice';
  end if;
  if not public.renew_paid_preparation('evt_prep',first_claim.preparation_token,120) then
    raise exception 'Current worker could not extend its preparation';
  end if;
  update public.paid_fulfillment_queue set preparation_expires_at = clock_timestamp() - interval '1 second'
    where processor_event_id='evt_prep';
  if public.renew_paid_preparation('evt_prep',first_claim.preparation_token) or
     public.finish_paid_preparation('evt_prep',first_claim.preparation_token,repeat('a',64),'private/old') or
     public.block_paid_preparation('evt_prep',first_claim.preparation_token,'stale') then
    raise exception 'Expired worker changed current work';
  end if;
  select * into recovered from public.claim_paid_preparation('worker-b');
  if recovered.processor_event_id is distinct from 'evt_prep'
     or recovered.preparation_token is not distinct from first_claim.preparation_token
     or recovered.preparation_attempts <> 2 then
    raise exception 'Crashed work was not recovered with a fresh token';
  end if;
  if public.finish_paid_preparation('evt_prep',first_claim.preparation_token,repeat('a',64),'private/old') then
    raise exception 'Old worker overwrote a replacement worker';
  end if;
  begin
    perform public.finish_paid_preparation('evt_prep',recovered.preparation_token,'bad','private/new');
    raise exception 'Malformed hash accepted';
  exception when invalid_parameter_value then null; end;
  if not public.finish_paid_preparation('evt_prep',recovered.preparation_token,repeat('b',64),'private/new') then
    raise exception 'Prepared artifact checkpoint failed';
  end if;
  if exists(select 1 from public.claim_paid_preparation('worker-c')) then
    raise exception 'Finished preparation was repeated';
  end if;
  if not exists(select 1 from public.paid_fulfillment_queue where processor_event_id='evt_prep'
     and status='pending' and prepared_sha256=repeat('b',64) and prepared_artifact_ref='private/new'
     and preparation_token is null and delivered_at is null and delivery_evidence_url is null) then
    raise exception 'Preparation lost checkpoint or was incorrectly counted as delivery';
  end if;
  if public.finish_paid_preparation('evt_prep',recovered.preparation_token,repeat('c',64),'private/overwrite') then
    raise exception 'Committed checkpoint was overwritten';
  end if;
  begin
    perform public.claim_paid_preparation(null,600);
    raise exception 'Null worker accepted';
  exception when invalid_parameter_value then null; end;
  begin
    perform public.claim_paid_preparation('worker',null);
    raise exception 'Null lease accepted';
  exception when invalid_parameter_value then null; end;
  begin
    perform public.claim_paid_preparation('worker',3601);
    raise exception 'Unbounded lease accepted';
  exception when invalid_parameter_value then null; end;
end $$;

insert into public.verified_revenue_events
  (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
values ('evt_block','003','stripe','invoice.paid','in_block','subscription_invoice',9900,'USD',now(),'in_block'),
       ('evt_retry','003','stripe','invoice.paid','in_retry','subscription_invoice',9900,'USD',now(),'in_retry');
do $$
declare work public.paid_fulfillment_queue;
begin
  select * into work from public.claim_paid_preparation('worker');
  if work.processor_event_id is distinct from 'evt_block' then raise exception 'Oldest work not first'; end if;
  begin
    perform public.block_paid_preparation('evt_block',work.preparation_token,' ');
    raise exception 'Empty blocker accepted';
  exception when invalid_parameter_value then null; end;
  if not public.block_paid_preparation('evt_block',work.preparation_token,'Buyer scope missing') then
    raise exception 'Could not preserve dependency';
  end if;
  select * into work from public.claim_paid_preparation('worker');
  if work.processor_event_id is distinct from 'evt_retry' then raise exception 'Blocked work re-entered claim queue'; end if;
  update public.paid_fulfillment_queue set preparation_attempts=5,
    preparation_expires_at=clock_timestamp()-interval '1 second' where processor_event_id='evt_retry';
  if exists(select 1 from public.claim_paid_preparation('worker')) then raise exception 'Retry limit ignored'; end if;
  if not exists(select 1 from public.paid_fulfillment_queue where processor_event_id='evt_retry'
    and status='blocked' and blocker like 'Preparation retry limit%' and preparation_token is null) then
    raise exception 'Exhausted work was silently abandoned';
  end if;
end $$;
reset role;
do $$
declare f regprocedure;
begin
  foreach f in array array['public.claim_paid_preparation(text,integer)'::regprocedure,
    'public.renew_paid_preparation(text,uuid,integer)'::regprocedure,
    'public.finish_paid_preparation(text,uuid,text,text)'::regprocedure,
    'public.block_paid_preparation(text,uuid,text)'::regprocedure] loop
    if has_function_privilege('anon',f,'EXECUTE') or has_function_privilege('authenticated',f,'EXECUTE')
      or not has_function_privilege('service_role',f,'EXECUTE') then
      raise exception 'Preparation permissions incorrect for %',f;
    end if;
    if (select prosecdef from pg_proc where oid=f) then raise exception 'Unnecessary privilege elevation'; end if;
  end loop;
end $$;
rollback;
