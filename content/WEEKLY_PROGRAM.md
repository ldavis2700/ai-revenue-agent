# First-of-month YouTube genre research; 10 original videos weekly

**Owner directive, November 10, 2026.** This supersedes the earlier 27-video and weekly-research quotas. On the **first of each month**, the existing research automation `Automation_c75fcc149fb48191bdbe64a5af38bbfb` samples recent YouTube genre performance. The existing hourly APEX wealth task `6a7e835492408191818a1f07ec08f4c6` develops, checks, and executes up to ten distinct original videos per week, distributed across all seven days: **2 Monday, 1 Tuesday, 2 Wednesday, 1 Thursday, 2 Friday, 1 Saturday, 1 Sunday**. The two existing automations are the only owners of these roles; do not create overlapping schedules.

## Monthly research evidence

Use current free sources, with a timestamped sample of at least three independent channels and canonical URLs, observed views, and observation dates. Compare current view growth, views per hour when known, repeatability and other genre candidates; distinguish Shorts from long-form and one-off news spikes. The chosen genre is a *best-supported winner in a limited sample*, **never** an invented global YouTube ranking. Reassess if evidence becomes unsafe or stale; retain the date, sample, methodological caveats, comparison and commercial-originality analysis. Researching a winning genre does not entitle APEX to copy other creators' scripts, footage, personas, music or thumbnails.

Record one monthly brief in the **existing private durable ledger** named `APEX_Weekly_YouTube_Ledger.sqlite`, stable `library_file_id`:
`libfile_fde3_f-d2af3ed854c48191b99423513ae69906_4ffc373f7d48819194014e1c99c4bf00`.
Never create a second private ledger, put the ledger in a public repo or overwrite its current version without optimistic concurrency. Fetch current `current_version_number`, materialize its bytes, run planner commands on it locally, replace **the same** library file using `expected_current_version` following each logical mutation. On conflict refetch and reconcile. If Library cannot expose this file, **do not** start a replacement or claim durable success.

The monthly research brief is a JSON object with `genre`, timezone-aware `researched_at`, and `sources` containing at least three independent `channel_id`s, canonical `https://www.youtube.com/watch?v=<11-char-id>` URLs, integer `views`, and timezone-aware `observed_at`. Record comparisons and limitations in additional fields; the planner validates structure, not underlying source authenticity. Do not invent a sample.

## Weekly operator commands

```sh
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite month --month 2026-12 --brief dated-monthly-sample.json
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite init --week 2026-12-07
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite assign --week 2026-12-07 --brief ten-distinct-concepts.json
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite status --week 2026-12-07
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite ready --slot 2026-12-07-01 --media-url https://HOST/artifacts/JOB/video.mp4
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite due
python scripts/weekly_video_plan.py --db /persistent/APEX_Weekly_YouTube_Ledger.sqlite receipt --slot 2026-12-07-01 --file actual-provider-receipt.json
```

The concepts JSON contains exactly 10 original differentiated `concepts` strings and optionally `genre`, matching the recorded research. Assignment requires documented monthly research for the **week-start month**. If an earlier week crosses month boundaries, keep its original month assignment and review the next complete week under the new genre.

When reading the **existing** 27-slot `2026-11-16` ledger, `init` migrates safely: keep all 27 rows and every receipt, mark only **unstarted** surplus slots inactive, and retime the first ten only if *no* slot has started. Started legacy work beyond target is retained and explicitly flagged; resolve conflicts rather than deleting progress or claiming ten-ready status. A retained inactive slot is not an active publishing commitment. All new weeks use ten rows. Do not attribute the past four public APEX uploads to any future weekly slot.

For each concept, create a useful manifest for the already-deployed content worker, test and deploy the reviewed commit, and inspect the finished video, full decode, captions, sound, claims, rights and original value before marking `ready`. Only one due candidate per hourly cycle; no backlog flood. Before attempting a provider publish, preserve the draft ID and exact revision in a durable operator checkpoint. If an operation times out or returns uncertain status, query its existing post first; never blindly retry. Import provider-completed receipts with `status`, `platform`, `video_id`, `post_url`, `publication_id`, `completed_at`, and `channel_id`; a published receipt does **not** establish YPP approval, payout or collected income.

## Destination, authorization and operating economics

Only publish to verified APEX-owned RMC AI Workshop channel `UC1TPDWauf7kEnOYjbE1zU7w`. The existing vidIQ tool requires a user-visible approval for each exact draft revision; standing owner publishing authorization does not bypass this provider requirement. Do not substitute HAEVEN's channel. Explore official authorized unattended free YouTube integrations without bypassing OAuth/MFA/approval, and do not claim automation is operational until end-to-end upload/receipt validation succeeds. YPP/AdSense, tax and payout status are **unverified**. No paid models, research credits, ads, courses or memberships; owner's lowest-necessary-hosting exception remains. Preserve Stripe pause, buyer-first work priority and material-only notifications. Source policy references: https://support.google.com/youtube/answer/1311392 and https://support.google.com/youtube/answer/72851 .
