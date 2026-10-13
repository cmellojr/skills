---
type: reference
resource: https://docs.cloud.google.com/free/docs/free-cloud-features
sources:
  - https://docs.cloud.google.com/free/docs/free-cloud-features
  - https://docs.cloud.google.com/billing/docs/how-to/budgets
verified: 2026-10-09
---

# Guardrails: alerts, quotas, and escalation

Defense in depth for keeping spend at $0. Read during Stage 4, when a
budget alert fires, or when planning enforcement.

## 1. Budget alerts (detection — never enforcement)

```bash
bash scripts/setup_guardrails.sh --billing-account <id> --project <id> --apply
```

Creates a budget with `percent=0.50`, `0.90`, `1.00` thresholds (1.0-based
gcloud values) scoped to the project. Notification recipients default to
billing account IAM users with billing permissions.

- **Budgets notify; they do not stop resources.** Crossing 100% keeps
  spending until someone acts.
- Budgets lag real usage by up to ~24h — treat thresholds as early warning,
  not real-time control.
- Free Trial accounts: spend stops automatically when the $300 credit runs
  out (projects are disabled), but that is a blunt, lossy cutoff.

## 2. Escalation ladder (when spend must stop)

1. Stop billable work: delete or stop VMs
   (`gcloud compute instances stop <name>`), scale Cloud Run to zero, pause
   Cloud SQL.
2. Disable billing on the project (billing account stays open):
   `gcloud billing projects disable --project=<id>` — resources are stopped
   and deletable after grace period rules.
3. Close the billing account as the last resort
   (`gcloud billing accounts close <id>`) — stops ALL billable services.

## 3. Quota awareness

Quotas cap usage before spend explodes. Review them in Stage 4 output or:

```bash
gcloud compute project-info describe --project <id>
```

Focus on `CPUS`, `DISKS_TOTAL_GB`, `IN_USE_ADDRESSES`. During the Free
Trial, quota increases are blocked — the quota ceiling is your hard limit.

## 4. Optional org policy constraints

If the project sits under a folder/org you control, these constraints
prevent non-free-tier resources outright:

- `constraints/compute.vmExternalIpAccess` — block VM external IPs (egress
  risk) except a allowlist.
- `constraints/compute.restrictLoadBalancerCreation` — block load balancers.
- `constraints/compute.allowedInstanceClass` or custom constraints via
  Organization Policy — restrict machine families (e.g. allow `e2-micro`
  only) where supported.
- `constraints/iam.allowedPolicyMemberDomains` and domain-scoped guardrails
  reduce accidental service enablement.

Single projects without org hierarchy: rely on stages 2–3 + budgets.

## 5. Recurring hygiene

- [ ] Run `scripts/audit_free_tier.py` weekly and before every deploy.
- [ ] Check Cloud Billing reports for the first days of each month (free
  tier counters reset on the 1st).
- [ ] Watch the 50 GiB/project log quota — verbose apps silently bill.
- [ ] Delete idle resources: orphaned disks, unattached static IPs,
  forgotten zonal VMs.
