# Monday research and 27 original videos per week

Owner instruction, November 10, 2026: research the most-viewed YouTube genres each
Monday, then create and publish 27 new original videos each week to an owner
channel that can pay the owner. Research begins Monday November 16, around 8 AM
America/Los_Angeles. Four slots Monday–Saturday and three Sunday total 27.

The active Monday automation is `Automation_c75fcc149fb48191bdbe64a5af38bbfb`.
The existing hourly APEX task `6a7e835492408191818a1f07ec08f4c6` executes the queue,
checks media and receipts, and repairs failures. No duplicate daily scheduler is
needed. These schedules have no end date; zero earnings do not stop work.

## Evidence and originality

Compare current seven-day view accumulation/velocity and total observed views;
separate Shorts from long-form. Cite dated observations from at least three
independent channels, disclose sampling limits and avoid calling a sampled winner
the proven global YouTube leader. Use free sources; paid hosting permission does
not authorize paid vidIQ research credits or paid model APIs. Create 27 distinct
concepts, original scripts and substantive visual examples. Borrow the genre and
viewer appeal, not other creators' expression. Do not fill a numerical quota with
low-value near-duplicates. Check YouTube monetization rules before production.

## Planner commands

Use an operator-controlled persistent DB, or export a reconciled snapshot to a
private durable location. Never treat a transient local DB as the deployed source
of truth. The CLI is an operator component, not a YouTube publishing client.

```
python scripts/weekly_video_plan.py --db /persistent/weekly.db init --week 2026-11-16
python scripts/weekly_video_plan.py --db /persistent/weekly.db assign --week 2026-11-16 --brief researched-brief.json
python scripts/weekly_video_plan.py --db /persistent/weekly.db ready --slot 2026-11-16-01 --media-url https://HOST/artifacts/JOB/video.mp4
python scripts/weekly_video_plan.py --db /persistent/weekly.db due
python scripts/weekly_video_plan.py --db /persistent/weekly.db receipt --slot 2026-11-16-01 --file actual-connector-receipt.json
python scripts/weekly_video_plan.py --db /persistent/weekly.db status --week 2026-11-16
```

The research brief includes `genre`, timezone-aware `researched_at`, `sources`
(each with canonical YouTube watch URL, channel_id, integer views, observed_at),
and exactly 27 distinct concept strings. Retain the full comparison, selection
rationale and evidence limitations in additional JSON fields. Do not invent
observations to pass validation. The planner validates structure/freshness; the
research workflow verifies source accuracy and independence.

For each assigned slot create a substantive manifest compatible with the hosted
renderer, test and deploy it, then review downloaded video, captions, rights and
claims before `ready`. The planner releases at most one due candidate per hourly
cycle and does not dump a backlog older than 24 hours. Missed slots require a
new staggered schedule and a reported shortfall, not hidden catch-up flooding.

Before publishing persist the provider draft/post ID and revision in the durable
operator run record. After errors or lost responses query the same post before
retrying. Import receipts only from the actual connector's completed publication:
`status`, `platform`, `video_id`, `post_url`, `publication_id`, `completed_at`,
`channel_id`. The ledger rejects duplicate video IDs and conflicting receipts.
Receipt metadata validation is not an independent platform query or proof of
revenue/payment. Reconcile against YouTube/provider state before counting success.

## Current verified account and blockers

APEX channel: RMC AI Workshop, @rmcapexai,
`UC1TPDWauf7kEnOYjbE1zU7w`. On November 10 the connector reported active publishing
access, 0 subscribers, 9 lifetime views and 3 public uploads. It does not expose
AdSense linkage, identity/tax/bank verification or payable balances. Payout status
is UNVERIFIED. Upload authorization is not payout authorization or YPP eligibility.

The connected vidIQ tool requires the user to have seen and approved the exact
post draft/revision. Standing owner permission does not remove that tool gate.
Prepare reviewable drafts while arranging a properly authorized unattended
integration; do not simulate approval or claim posts were scheduled. Metricool's
connected YouTube account belongs to the HAEVEN brand and has a different channel
ID, so do not substitute it for APEX. Any native unattended upload integration
needs its own legitimate OAuth access and free quota verification.

YouTube ad revenue requires YPP eligibility and approval plus the appropriate
AdSense connection. Account-owner identity/tax/bank/contract steps cannot be
fabricated. Keep production going while eligibility develops; report publication,
monetization approval, accrued revenue and received payouts separately.
Official references checked November 10, 2026:
- https://support.google.com/youtube/answer/72851
- https://support.google.com/youtube/answer/9914702
- https://support.google.com/youtube/answer/1311392
