# Monthly YouTube genre review and ten originals per week

**Current instruction, November 10, 2026:** On the first of each month, use a dated, reproducible sample of public YouTube viewing to identify the genre attracting the most *observed* views, comparing Shorts and long-form separately. The monthly research task is `Automation_c75fcc149fb48191bdbe64a5af38bbfb`; the existing hourly execution task `6a7e835492408191818a1f07ec08f4c6` owns production and publication. No duplicate scheduler. Monthly research begins December 1, 2026; avoid inventing an unresearched winner before then.

The current weekly target is **ten** differentiated, substantial, original videos (two Monday, one Tuesday, two Wednesday, one Thursday, one Friday, two Saturday, one Sunday). Genre research happens monthly, not weekly. The monthly evidence must include at least three independent YouTube channels, canonical video links, observations with timestamps and integer view counts, sample limitations, Shorts/long-form comparison and observable view velocity when obtainable. Evidence can only justify a winner *within the sampled set*, not a universal YouTube-wide ranking.

## Existing private ledger: preservation is mandatory

Reuse the existing `APEX_Weekly_YouTube_Ledger.sqlite` in Library, canonical ID `libfile_fde3_f-d2af3ed854c48191b99423513ae69906_4ffc373f7d48819194014e1c99c4bf00`. Read/materialize its latest version before changes and upload an exact-version replacement; on conflict reload and reconcile. The preexisting 2026-11-16 week contains **27 historical unassigned slots**. The planner migrates without deleting records, deactivates only untouched excess slots and distributes the remaining ten untouched slots across the week. A prepared/published surplus record is retained; no customer or provider receipt is deleted. Do not create a second ledger, infer that initialized slots are videos, or report a draft as posted.

## Planner examples

```sh
python scripts/weekly_video_plan.py --db /persistent/weekly.db month --month 2026-12 --brief monthly-observed-genre.json
python scripts/weekly_video_plan.py --db /persistent/weekly.db init --week 2026-12-07
python scripts/weekly_video_plan.py --db /persistent/weekly.db assign --week 2026-12-07 --brief ten-original-concepts.json
python scripts/weekly_video_plan.py --db /persistent/weekly.db due
python scripts/weekly_video_plan.py --db /persistent/weekly.db receipt --slot 2026-12-07-01 --file verified-provider-receipt.json
```

The month brief requires a genre, `researched_at`, and `sources` with `channel_id`, canonical `url`, integer `views` and `observed_at`. The week brief requires the *same* monthly genre and exactly ten unique concepts. Never manufacture a source observation or claim a new monthly study was done when absent. Weekly assignments are immutable after they are made; monthly observations cannot silently overwrite active work.

Each content job goes through original-script and rights checks, local free narration/render, full decode, factual/visual/audio QA, then only authorized account publishing. The worker is not the publisher. Persist draft/revision before sending. vidIQ currently requires the owner to see and approve each exact revision; general owner permission cannot substitute for a provider gate. Reconcile uncertain post status before retrying, and only count complete provider receipts. Never replay a backlog flood. Keep the channel RMC AI Workshop `UC1TPDWauf7kEnOYjbE1zU7w` separate from HAEVEN accounts.

Payout status is unverified. YouTube posting or views are not earned cash. Retain existing owner spending limits, Stripe pause and material-only notifications. Paid hosting exception covers the existing minimum worker only, not paid research, generative APIs, ads or Connects.

Official policy references: https://support.google.com/youtube/answer/1311392 (originality/inauthentic content), https://support.google.com/youtube/answer/72851 (partner eligibility), https://support.google.com/youtube/answer/14328491 (synthetic content disclosure).
