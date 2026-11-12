-- Preparation only: a lease never authorizes a send, charge, or delivery status.
alter table public.paid_fulfillment_queue
  add column preparation_attempts integer not null default 0 check (preparation_attempts >= 0),
  add column preparation_token uuid,
  add column preparation_worker text,
  add column preparation_expires_at timestamptz,
  add column prepared_sha256 text,
  add column prepared_artifact_ref text,
  add column prepared_at timestamptz,
  add constraint preparation_lease_complete check (
    (preparation_token is null and preparation_worker is null and preparation_expires_at is null)
    or (preparation_token is not null and preparation_worker is not null
        and length(trim(preparation_worker)) between 1 and 128 and preparation_expires_at is not null)
  ),
  add constraint prepared_artifact_complete check (
    (prepared_at is null and prepared_sha256 is null and prepared_artifact_ref is null)
    or (prepared_at is not null and prepared_at >= created_at
        and prepared_sha256 is not null and prepared_sha256 ~ '^[0-9a-f]{64}$'
        and prepared_artifact_ref is not null and length(trim(prepared_artifact_ref)) between 1 and 1024)
  );

create function public.claim_paid_preparation(p_worker text, p_lease_seconds integer default 600)
returns setof public.paid_fulfillment_queue
language plpgsql security invoker set search_path = '' as $$
begin
  if p_worker is null or length(trim(p_worker)) not between 1 and 128
     or p_lease_seconds is null or p_lease_seconds not between 60 and 3600 then
    raise exception 'Invalid worker or lease duration' using errcode = '22023';
  end if;

  -- Exhausted crashed work is visible, not silently dropped or retried forever.
  with exhausted as (
    select q.processor_event_id from public.paid_fulfillment_queue q
    where q.status = 'pending' and q.prepared_at is null
      and q.preparation_attempts >= 5
      and (q.preparation_expires_at is null or q.preparation_expires_at <= clock_timestamp())
    for update skip locked
  )
  update public.paid_fulfillment_queue q
    set status = 'blocked', blocker = 'Preparation retry limit reached; inspect attempts before resuming',
        preparation_token = null, preparation_worker = null, preparation_expires_at = null
    from exhausted e where q.processor_event_id = e.processor_event_id;

  return query
  with candidate as (
    select q.processor_event_id from public.paid_fulfillment_queue q
    where q.status = 'pending' and q.prepared_at is null and q.preparation_attempts < 5
      and (q.preparation_expires_at is null or q.preparation_expires_at <= clock_timestamp())
    order by q.created_at, q.processor_event_id
    limit 1 for update skip locked
  )
  update public.paid_fulfillment_queue q
    set preparation_token = gen_random_uuid(), preparation_worker = trim(p_worker),
        preparation_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
        preparation_attempts = q.preparation_attempts + 1, blocker = null
    from candidate c where q.processor_event_id = c.processor_event_id
    returning q.*;
end;
$$;

create function public.renew_paid_preparation(p_event_id text, p_token uuid, p_lease_seconds integer default 600)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
  if p_lease_seconds is null or p_lease_seconds not between 60 and 3600 then
    raise exception 'Invalid lease duration' using errcode = '22023';
  end if;
  update public.paid_fulfillment_queue q
    set preparation_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds)
    where q.processor_event_id = p_event_id and q.preparation_token = p_token
      and q.preparation_expires_at > clock_timestamp() and q.status = 'pending' and q.prepared_at is null;
  return found;
end;
$$;

create function public.finish_paid_preparation(p_event_id text, p_token uuid, p_sha256 text, p_artifact_ref text)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
  if p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$'
     or p_artifact_ref is null or length(trim(p_artifact_ref)) not between 1 and 1024 then
    raise exception 'Valid artifact hash and durable reference required' using errcode = '22023';
  end if;
  update public.paid_fulfillment_queue q
    set prepared_sha256 = p_sha256, prepared_artifact_ref = trim(p_artifact_ref), prepared_at = clock_timestamp(),
        preparation_token = null, preparation_worker = null, preparation_expires_at = null
    where q.processor_event_id = p_event_id and q.preparation_token = p_token
      and q.preparation_expires_at > clock_timestamp() and q.status = 'pending' and q.prepared_at is null;
  return found;
end;
$$;

create function public.block_paid_preparation(p_event_id text, p_token uuid, p_reason text)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
  if p_reason is null or length(trim(p_reason)) not between 1 and 2048 then
    raise exception 'Specific blocker required' using errcode = '22023';
  end if;
  update public.paid_fulfillment_queue q
    set status = 'blocked', blocker = trim(p_reason),
        preparation_token = null, preparation_worker = null, preparation_expires_at = null
    where q.processor_event_id = p_event_id and q.preparation_token = p_token
      and q.preparation_expires_at > clock_timestamp() and q.status = 'pending' and q.prepared_at is null;
  return found;
end;
$$;

revoke all on function public.claim_paid_preparation(text,integer),
  public.renew_paid_preparation(text,uuid,integer),
  public.finish_paid_preparation(text,uuid,text,text),
  public.block_paid_preparation(text,uuid,text) from public, anon, authenticated;
grant execute on function public.claim_paid_preparation(text,integer),
  public.renew_paid_preparation(text,uuid,integer),
  public.finish_paid_preparation(text,uuid,text,text),
  public.block_paid_preparation(text,uuid,text) to service_role;

comment on function public.claim_paid_preparation(text,integer) is
  'Server-only preparation reservation. Expired attempts can be replayed. Never send, charge or perform external side effects under this lease; those need separate delivery idempotency and reconciliation.';
