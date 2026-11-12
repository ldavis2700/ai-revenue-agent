"""Exercise real concurrent Postgres sessions in disposable CI, never production."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor


def sql(statement):
    return subprocess.run(['psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-c', statement],
                          check=True, capture_output=True, text=True, timeout=15).stdout.strip()


def main():
    if os.getenv('APEX_DISPOSABLE_POSTGRES') != '1' or os.getenv('PGDATABASE') != 'apex_test':
        raise SystemExit('Requires explicitly disposable apex_test database')
    sql("""grant usage on schema public to service_role;
        insert into public.verified_revenue_events
        (processor_event_id,property_id,processor,event_type,payment_reference,revenue_kind,amount_cents,currency,occurred_at,source_object_id)
        select 'evt_concurrent_'||n,'003','stripe','invoice.paid','in_concurrent_'||n,
          'subscription_invoice',9900,'USD',now(),'in_concurrent_'||n from generate_series(1,4) n;""")
    locker = subprocess.Popen(['psql', '-XAt', '-v', 'ON_ERROR_STOP=1'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        locker.stdin.write("begin; select processor_event_id from public.paid_fulfillment_queue "
                           "where processor_event_id='evt_concurrent_1' for update;\n\\echo LOCKED\n")
        locker.stdin.flush()
        while True:
            line = locker.stdout.readline()
            if not line:
                raise AssertionError('Locking session exited before acquiring row lock')
            if line.strip() == 'LOCKED':
                break
        def claim(n):
            result = sql(f"set role service_role; select processor_event_id from public.claim_paid_preparation('ci-{n}');")
            return [line for line in result.splitlines() if line.startswith('evt_')]
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = [event for result in pool.map(claim, range(8)) for event in result]
        assert len(claims) == len(set(claims)) == 3, claims
        assert 'evt_concurrent_1' not in claims, claims
        locker.stdin.write('commit;\n\\q\n')
        locker.stdin.flush()
        locker.wait(timeout=10)
        assert locker.returncode == 0
        assert claim(9) == ['evt_concurrent_1']
        assert claim(10) == []
        print('PASS: concurrent workers claim distinct work, skip locked rows, and resume unlocked work')
    finally:
        if locker.poll() is None:
            locker.kill()
            locker.wait(timeout=10)
        sql("delete from public.paid_fulfillment_queue where processor_event_id like 'evt_concurrent_%';"
            "delete from public.verified_revenue_events where processor_event_id like 'evt_concurrent_%';")


if __name__ == '__main__':
    main()
