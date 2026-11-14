# APEX creative strategy handoff: fictional offline demonstration

This **original, local standard-library example** shows one narrowly bounded intake-to-review checkpoint. It is a capability demonstration for prospective buyer work, **not** an actual customer contract, production deployment, published ad, launched funnel, automated approval, invoicing or income. The client, evidence, costs, reviewers, briefs and domain paths in `sample_fictional.json` are **fictional fixtures**; `example.org` is not an authoritative pricing or creative source.

Run from this folder with Python 3.10+:

```bash
python creative_handoff_demo.py --input sample_fictional.json
python -m unittest -v test_creative_handoff_demo
```

**Workflow:** source map / client context → separately owned ad and funnel strategy → production/editor handoff → **separate human creative review** → reviewer-only manual handoff → explicit human publication decision outside this demo. Ad and funnel artifacts share a context identifier but never share an approval state. The script refuses to mark any track review-ready until the client and version match, named owners and evidence links exist, two human review flags are supplied, and every listed tool cost has an explicit amount and traceable pricing URL. A fake `true` approval flag is still merely an input claim; no account authorization, source truth or rights are authenticated. Each item gets a repeatable SHA-256 of its canonical input, useful for detecting handoff changes. All outputs unconditionally set `external_action_allowed=false`.

**Sample walkthrough:** the ad remains blocked for a creative reviewer; the funnel has both fictional review flags and appears `ready_for_manual_handoff` but is still **not** eligible for automatic external execution. Output includes blockers, a named next actor, source-bound content hash and a declared line-item cost; these are only fixture data, not real expenses.

**Restart note:** a team member should reopen the latest approved client context, verify origin, version and rights, check that every lane's review flags correspond to genuine human approvals, rerun this CLI, and compare item hashes with the previously reviewed packet. If anything changed, invalidate old approvals and seek new review. Never copy any customer's confidential inputs into a public repository. A real engagement needs written scope, permissioned project access, proper confidentiality controls, delivery/QA acceptance, verified invoicing, and an independently tested integration in the **buyer's own authorized tools**.

**Cost boundary:** platform tokens/Connects, freelancer fees, hosting allocations, tool/API usage, production/editor labor, review/support time and refunds must be separately priced for a real buyer. An unresolved cost is not zero. This script only checks the hypothetical `tool_costs` passed in; it does **not** estimate or audit real marketplace fees, legal/licensing scope, or general economics.
