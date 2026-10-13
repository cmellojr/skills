---
name: gcp-free-tier
description: >
  Guardrails to keep a Google Cloud project strictly within the Free Tier.
  Audits live resources against official monthly limits (Compute Engine
  e2-micro hours, US-only regions, disk and egress quotas), vets deployment
  plans and IaC before creation, and configures billing budget alerts and
  quota checks as safeguards. Refreshes limits from the official Google
  Cloud Free Program documentation. Activate when deploying to Google Cloud
  on a free or trial billing account, auditing a project for cost overruns,
  or preventing unexpected cloud charges.
license: Apache-2.0
metadata:
  category: devops
  tags: "google-cloud, free-tier, cost-control, billing, quotas, devops"
  author: Carlos Mello Jr (cmellojr@gmail.com)
  version: "1.0.0"
  canonical: https://github.com/cmellojr/skills/tree/main/gcp-free-tier/
compatibility: Requires gcloud CLI and read access to the project and billing account
---

# Google Cloud Free Tier Guardrails

Keep a Google Cloud project inside the Free Tier: refresh limits from the
official docs, audit live resources, veto out-of-scope deployments, and arm
billing budget alerts. Free Tier usage is calculated **per billing account,
per calendar month**, with **no rollover** — anything above the limits is
billed at standard rates.

## Available scripts

- `scripts/audit_free_tier.py` — read-only audit of live resources against
  Free Tier structural limits. Emits JSON to stdout; exit `1` on violations,
  `2` on tooling/auth errors.
- `scripts/setup_guardrails.sh` — creates a Cloud Billing budget alert and
  prints quota usage. Dry-run by default; pass `--apply` to make changes.

```bash
# Audit a project (JSON report to stdout)
uv run scripts/audit_free_tier.py --project my-project

# Include the budget check for a billing account
uv run scripts/audit_free_tier.py --project my-project --billing-account 012345-6789AB-CDEF01

# Preview guardrail commands, then apply them
bash scripts/setup_guardrails.sh --billing-account 012345-6789AB-CDEF01 --project my-project
bash scripts/setup_guardrails.sh --billing-account 012345-6789AB-CDEF01 --project my-project --apply
```

If `uv` is unavailable, run with plain `python3` (stdlib only).

## Workflow

### Stage 1 — Refresh limits from the official docs

1. Fetch `https://docs.cloud.google.com/free/docs/free-cloud-features`.
2. Read the `verified:` date in `references/free-tier-limits.md`.
3. If the live table differs from the snapshot (limits change with 30 days'
   notice), update the snapshot, bump `metadata.version`, and note the new
   date. Always audit against the freshly fetched numbers.

### Stage 2 — Audit the live project

1. Run `uv run scripts/audit_free_tier.py --project <id>` (add
   `--billing-account <id>` when known).
2. Exit `0`: no structural violations. Exit `1`: fix every violation, then
   re-run. Exit `2`: fix tooling/auth first (see Failure recovery).
3. Warnings (estimated e2-micro hours, missing budget) require manual
   follow-up — they do not fail the audit.

### Stage 3 — Pre-deploy gate

Veto any command, Terraform plan, or manifest that fails this checklist
against `references/free-tier-limits.md` and `references/dangerous-resources.md`:

- [ ] Instance is `e2-micro`, non-preemptible, in `us-west1`/`us-central1`/`us-east1`
- [ ] Boot disk is `pd-standard`; total standard disk <= 30 GB
- [ ] No GPU/TPU, no Cloud SQL, no Memorystore, no load balancer
- [ ] Cloud Storage buckets are in `us-east1`/`us-west1`/`us-central1`
- [ ] Product has a Free Tier entry and this month's usage is still under it
- [ ] Region is US for anything with region-pinned Free Tier limits
- [ ] Egress estimates stay within the North America monthly allowances

If a step fails: propose the free-tier-compliant alternative (e.g.
`--machine-type=e2-micro --boot-disk-type=pd-standard --zone=us-central1-a`)
or stop and report the cost risk.

### Stage 4 — Guardrails

1. Run `bash scripts/setup_guardrails.sh --billing-account <id> --project <id>`
   (dry-run), review the printed commands, re-run with `--apply`.
2. This creates a `$1` budget with 50% / 90% / 100% email thresholds scoped
   to the project, and prints current compute quotas.
3. Budget alerts **notify only — they never stop resources**. Read
   `references/guardrails.md` for escalation steps (stop VMs, disable
   billing) and optional org policy constraints.

## Validation loop

Re-run the audit after every remediation until it exits `0`:

```bash
uv run scripts/audit_free_tier.py --project my-project && echo "FREE TIER OK"
```

## Report template

```markdown
# Free Tier audit — <project-id> — <date>
- Result: PASS | FAIL (exit code)
- Violations: <n> | Warnings: <n> | Skipped checks: <n>
| Severity | Rule | Resource | Detail | Fix |
|---|---|---|---|---|
| violation | vm-region | instance-1 | in europe-west1 | recreate in us-central1 |
- Follow-up: <warnings, usage-based limits to watch in Billing reports>
```

## Gotchas & edge cases

- The `e2-micro` Free Tier limit is **by hours, not instance count**: all
  `e2-micro` instances combined may run for at most the hours in the month.
- Free Tier is per **billing account**, not per project. Multiple projects
  on one account share the limits.
- Limits do not roll over between months; Google may change them with 30
  days' notice.
- Cloud Storage Free Tier applies **only** to `us-east1`, `us-west1`,
  `us-central1` (combined); other regions and multi-region US may be billed.
- GPUs and TPUs are **always billed**, never Free Tier. The $300 trial
  credit cannot pay for GPUs either (blocked during Free Trial).
- The GKE credit covers the **cluster fee only** — node compute, networking
  and storage are billed.
- The $300/90-day Free Trial is not the Free Tier: over-limit usage drains
  the credit, and when it expires billing stops and resources are deleted
  after a 30-day grace period.
- Usage-based limits (Cloud Run requests, BigQuery bytes, logs 50 GiB) are
  invisible to resource inventory — verify them in Cloud Billing reports.

## Failure recovery

- `gcloud: command not found` / auth errors: install the Google Cloud CLI
  (`https://docs.cloud.google.com/sdk/docs/install-sdk`) and run
  `gcloud auth login` (plus `gcloud auth application-default login` for ADC).
- Permission denied on a check: the audit needs read access
  (`roles/viewer` on the project; `billing.accounts.getSpending`/budget
  viewer for the budget check). Skipped checks are listed under
  `checks_skipped` in the JSON — never treat a skipped check as a pass.
- Budget check unavailable: `gcloud billing budgets` may require the Beta
  component or Budget Viewer on the billing account; the audit records it
  as skipped and continues.
