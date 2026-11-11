# Continuous content hosting

The owner authorized the least expensive viable paid hosting on November 10,
2026. Free publishing accounts and free tools remain mandatory. This exception
covers hosting, not paid AI APIs, advertising, or other subscriptions.

`Dockerfile.content` runs a persistent original-content queue, FFmpeg rendering,
local Flite narration, and a minimal health/artifact server. No AI API or model
subscription is required. It renders checked-in original lesson manifests once,
then waits for new jobs. It does not invent endless scripts, republish duplicates,
connect social accounts, or enable channel monetization by itself.

## Deployment

Dedicated Railway service `apex-content-worker` in `apex-ultra-isolated`, separate
from the APEX ULTRA API. Use one replica, 0.1 vCPU, 0.25 GB memory, 1 GB volume at
`/data`, sleep disabled, restart ALWAYS, `/health` on port 8080. Pin the verified
commit; deploy subsequent reviewed manifest additions explicitly. Startup prepares
only the dedicated content directory then drops privileges to uid/gid 10001.

Railway Hobby currently has a $5 monthly minimum, including $5 usage, not an
unlimited flat fee. At November 10 published rates, this service's CPU/memory
limits approximate $4.50 per 30-day month at continuous maximum consumption,
plus about $0.15 for 1 GB stored and up to about $0.15 for 100 MB/day media egress.
These estimates are service-specific, exclude taxes, month-length variation and
other services, and are not an account billing cap. Other existing services share
the account bill. Do not upgrade the account or raise limits merely to increase
output. Measure actual use and throughput first.
Sources: https://railway.com/pricing and https://docs.railway.com/pricing/plans

## Daily operation

The owner's hourly automation researches useful original lessons, checks claims
and rights, writes unique JSON jobs to `content/jobs`, validates them, and deploys
the reviewed revision. Each job states its audience, rights and synthetic voice
use. Topic selection and editorial judgment remain in that workflow. IDs are
immutable; content digests reject accidental duplicates with new IDs. The worker
checks its local queue every five minutes, runs one render at a time and remains
online when the queue is empty or earnings are zero.

`/health` exposes only aggregate queue counts; detailed `/admin/jobs` and
`/artifacts/<job-id>/video.mp4`, `captions.srt`, and `manifest.json` require the
private `Authorization: Bearer` token in `CONTENT_ARTIFACT_TOKEN`. If the token
is absent, access fails closed. An unauthorized request cannot consume egress.
Before deploying this reviewed change, provision that secret in the content
worker's Railway environment and securely configure each approved consumer;
do not commit, log or share the token in tickets. Do not change the live service
until required provider approval and private-consumer acceptance pass.

The no-redirect, no-overwrite operator client is
`scripts/fetch_content_artifact.py`. With a securely configured local environment
variable `CONTENT_ARTIFACT_TOKEN`, fetch a reviewed asset using:

```
python scripts/fetch_content_artifact.py stop-duplicate-automation-20261110 video.mp4 ./original.mp4 --sha256 <pre-recorded-sha256>
```

The script targets only the approved Railway host, never follows redirects,
streams into an atomic temporary file, enforces a bounded size and optionally
verifies the pre-recorded SHA-256 before committing the file. Its local nine-test
suite runs with `python -m unittest discover -s tests -p test_fetch_content_artifact.py -v`.
Only completed artifacts are served, with an atomic persistent 100 MB/day
transfer allowance. Artifacts contain no customer records or credentials.
Publication is a separate
step using an authorized channel connector after visual/audio/claims checks;
provider-required approvals must not be fabricated. Store each resulting post ID
and URL to prevent duplicate publication. A completed render is not a published
video, monetization approval, or income.

Storage pauses new renders above 600 MB or below 150 MB free. Unpublished outputs
are preserved; archive completed media and verify publication receipts before
removing old artifacts. Three failed attempts hold an individual job for repair;
other jobs continue. Attempts are separated by at least an hour. SIGTERM kills
active encoders; durable interrupted jobs resume after restart. Create `/data/content/pause`
to pause rendering without deleting jobs. Remove it to resume. Never infer that
lack of revenue is a stop condition.

## Read-only release acceptance

The combined APEX Response Lab/private-artifact revision includes a bounded,
read-only HTTP preflight. It does **not** deploy code, send customer inquiries,
activate checkout, publish media or prove a payout. After normal provider approval
and isolated preview setup, run against the exact verified owned origin:

```
python scripts/verify_response_lab.py --origin https://apex-content-worker-production.up.railway.app --job-id stop-duplicate-automation-20261110
```

The private token is read **only** from the local `CONTENT_ARTIFACT_TOKEN`
environment, never a command-line argument or output. Run this after the
reviewed code is available at the chosen target; the older live deployment is
expected to fail preflight. The script permits that exact Railway origin or
a local `127.0.0.1` test server, and rejects redirects and other hosts before
sending a credential. It checks the public academy, stylesheet, builder,
privacy, paused checkout, aggregate-only health, inaccessible source/database,
anonymous private-route denial and a known completed **manifest** with
authorized credentials. The manifest GET consumes some of the existing
bounded egress allowance; it does not download a video. Missing token or
known job ID is **not** a passing release. A green local/HTTP preflight alone
does not replace exact-commit CI, private-consumer authorization, Railway
confirmation, rollback review, or actual receipt verification.

The isolated regression suite is
`python -m unittest discover -s tests -p test_verify_response_lab.py -v`.
No customer or financial data is needed for it.

## Validation

Run `python -m unittest discover -s tests -p test_content_worker.py -v`.
CI additionally builds the exact container and renders a real original lesson
with a 256 MB memory limit. Runtime performs a full decode before recording the
artifact as complete. It records duration, size and SHA-256. Inspect sampled
frames and listen to the narration before each first publication.
