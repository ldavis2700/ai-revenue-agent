#!/usr/bin/env python3
"""One evidence-based APEX self-improvement review daily, no external actions.

Reads the *existing* private revenue ledger; never synthesizes external receipts,
runs arbitrary tasks, installs packages, or changes approval/spending controls.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

MAX_SAMPLED_RUNS=50
VALID_STATUSES={"completed","failed","timed_out","interrupted","degraded"}

def _tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}

def _choose_bottleneck(db):
    tables=_tables(db)
    if "revenue_worker_runs" not in tables:
        return {"category":"runtime_observability","evidence":"worker run history unavailable",
                "next_test":"Verify the existing persistent worker state and heartbeat on the authorized runtime."}
    # The self-review runs *inside* the current cycle. Its in-progress
    # "running" record is not evidence of a completed, failed, or paid cycle.
    rows=db.execute(
        "SELECT status,stages_json FROM revenue_worker_runs "
        "WHERE status != 'running' ORDER BY id DESC LIMIT ?",
        (MAX_SAMPLED_RUNS,)).fetchall()
    if not rows:
        return {"category":"runtime_observability","evidence":"zero finalized production cycles",
                "next_test":"Verify actual continuous worker startup and durable cycle receipts on an authorized host."}
    failures=Counter()
    for state,raw in rows:
        if state not in VALID_STATUSES:
            failures["invalid_cycle_status"]+=1
        elif state in ("failed","timed_out","degraded","interrupted"):
            failures["cycle:"+state]+=1
        if not raw:
            continue
        try:
            stages=json.loads(raw)
        except (ValueError,TypeError):
            failures["invalid_stages_json"]+=1
            continue
        if not isinstance(stages,list):
            failures["invalid_stages_json"]+=1
            continue
        for item in stages:
            if not isinstance(item,dict):
                failures["invalid_stage_record"]+=1
                continue
            st=item.get("status")
            name=item.get("stage")
            if st in ("failed","timed_out","interrupted"):
                # Never persist raw diagnostics or action payloads.
                if name in ("learn","plan","execute_authorized_inbound","self_review"):
                    failures[f"{name}:{st}"]+=1
                else:
                    failures["unknown_stage_failure"]+=1
    if failures:
        biggest=sorted(failures.items(),key=lambda p:(-p[1],p[0].startswith("cycle:"),p[0]))[0]
        return {"category":"reliability","evidence":f"{biggest[0]} observed in {biggest[1]} of {len(rows)} sampled cycles",
                "next_test":"Reproduce this bounded failure with synthetic fixtures; add regression test, then prepare reviewed PR. Do not replay uncertain external effects."}
    if "payment_receipts" not in tables or "recurring_payment_receipts" not in tables:
        return {"category":"collection_coverage","evidence":"local payment receipt schema or source coverage unverified",
                "next_test":"Read actual authorized payment-provider receipts and reconcile current ledger coverage without inventing a sale."}
    paid=(db.execute("SELECT COUNT(*) FROM payment_receipts").fetchone()[0]+
          db.execute("SELECT COUNT(*) FROM recurring_payment_receipts").fetchone()[0])
    if paid==0:
        return {"category":"first_paid_delivery","evidence":f"{len(rows)} recorded cycles, no local receipt rows",
                "next_test":"Validate a genuine buyer request, accepted scoped delivery, and a permitted non-Stripe collection route; no unsolicited contact."}
    return {"category":"realized_profitability","evidence":f"{paid} local payment rows; external settlement and actual profit not verified by this audit",
            "next_test":"Independently reconcile settled receipts, refunds, delivery/support costs and repeat paying customers before scaling."}

def record_review(db, review_day):
    if not isinstance(review_day,str) or len(review_day)!=10 or review_day[4]!="-" or review_day[7]!="-":
        raise ValueError("expected UTC YYYY-MM-DD date")
    try:
        if datetime.strptime(review_day,"%Y-%m-%d").strftime("%Y-%m-%d")!=review_day:
            raise ValueError("invalid date")
    except ValueError:
        raise ValueError("invalid review date")
    # A transaction lock ensures one daily record across overlapping cycles.
    db.execute("BEGIN IMMEDIATE")
    db.execute("""CREATE TABLE IF NOT EXISTS apex_self_improvement_reviews(
        day_utc TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        priority TEXT NOT NULL,
        evidence TEXT NOT NULL,
        next_test TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'proposed'
    )""")
    existing=db.execute("SELECT priority,evidence,next_test FROM apex_self_improvement_reviews WHERE day_utc=?",(review_day,)).fetchone()
    if existing:
        db.commit()
        return {"day_utc":review_day,"recorded":False,"priority":existing[0],
                "evidence":existing[1],"next_test":existing[2]}
    b=_choose_bottleneck(db)
    stamp=datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO apex_self_improvement_reviews(day_utc,created_at,priority,evidence,next_test) VALUES (?,?,?,?,?)",
               (review_day,stamp,b["category"],b["evidence"],b["next_test"]))
    db.commit()
    return {"day_utc":review_day,"recorded":True,"priority":b["category"],
            "evidence":b["evidence"],"next_test":b["next_test"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",default=os.getenv("REVENUE_DB_PATH","/files/data/revenue_agent.db"))
    p.add_argument("--day")
    args=p.parse_args()
    path=Path(args.db)
    if not path.is_file():
        p.error("Existing persistent revenue ledger required; will not create a new one")
    today=datetime.now(timezone.utc).date().isoformat()
    day=args.day or today
    with sqlite3.connect(str(path),timeout=10) as db:
        result=record_review(db,day)
    print(json.dumps({**result,"executed_external_action":False,
                      "independently_verified_revenue":False,
                      "production_deployment_performed":False},sort_keys=True))

if __name__=="__main__":
    main()
