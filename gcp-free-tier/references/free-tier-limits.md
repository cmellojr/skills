---
type: reference
resource: https://docs.cloud.google.com/free/docs/free-cloud-features
sources:
  - https://docs.cloud.google.com/free/docs/free-cloud-features
verified: 2026-10-09
---

# Free Tier usage limits (snapshot)

Monthly limits per **billing account**. No rollover. Usage above a limit is
billed at standard rates. Refresh this snapshot from the `resource` URL
whenever the live page differs (Stage 1 of SKILL.md).

## Always Free products

| Product | Free Tier limit |
|---|---|
| App Engine (Standard) | 28 h/day of F1 instances, 9 h/day of B1, 1 GB egress/day |
| Artifact Registry | 0.5 GB storage/month |
| BigQuery | 1 TiB querying/month, 10 GiB storage/month |
| Cloud Build | 2,500 build-minutes/month (`e2-standard-2`) |
| Cloud Deploy | First active delivery pipeline per billing account |
| Cloud KMS | 100 active key versions/month, 10,000 cryptographic operations/month (Autokey) |
| Cloud Logging & Monitoring | 50 GiB logs/project/month, default retention free, 1M Monitoring read calls/billing account |
| Cloud Natural Language API | 5,000 units/month |
| Cloud Run (request-based) | 2M requests, 360,000 GB-s memory, 180,000 vCPU-s, 1 GB egress from North America |
| Cloud Run functions | 2M invocations, 400,000 GB-s, 200,000 GHz-s, 5 GB egress/month |
| Cloud Shell | Free instance + 5 GB persistent disk |
| Cloud Source Repositories | 5 users, 50 GB storage, 50 GB egress/month |
| Cloud Storage | 5 GB-months regional (US only), 5,000 Class A + 50,000 Class B ops, 100 GB egress from NA. **Only** `us-east1`, `us-west1`, `us-central1` (combined) |
| Cloud Vision API | 1,000 units/month |
| Compute Engine | 1 non-preemptible `e2-micro` VM in `us-west1`/`us-central1`/`us-east1`; 30 GB-months standard persistent disk; 1 GB egress from NA. Hours-based limit (combined across the 3 regions). **No GPUs/TPUs** |
| Datastream | 100 GiB CDC/month (AlloyDB/Spanner to BigQuery only) |
| Firestore | 1 GiB storage, 50k reads / 20k writes / 20k deletes per day, 10 GiB egress/month (per project) |
| GKE | 1 free Autopilot or zonal Standard cluster/month (**cluster fee only**) |
| Pub/Sub | 10 GiB messages/month |
| reCAPTCHA | 10,000 assessments/month |
| Secret Manager | 6 active secret versions, 10,000 access ops, 3 rotation notifications/month |
| Security Command Center | Standard tier baseline scanning |
| Speech-to-Text | 60 minutes/month (V1 API) |
| Video Intelligence API | 1,000 units/month |
| Web Risk | 100,000 `uris.search` calls/month |
| Workflows | 5,000 internal steps, 2,000 external HTTP calls/month |
| Workload Manager | 5,000 resource evaluations/month |
| Agent Runtime (Gemini Enterprise Agent Platform) | 180,000 vCPU-s + 360,000 GiB-s/month |
| Application Integration | 400 executions, 20 GiB processed, 2 Google service nodes |

Products not listed here have no Free Tier — check the product's pricing
page before deploying.

## Free Trial ($300 / 90 days) — not Free Tier

- $300 welcome credit, valid 90 days; no billing while the trial lasts.
- **Blocked during trial**: GPUs, Cloud Marketplace, quota increases,
  Windows Server VMs, VMware Engine, generative AI model-as-a-service.
- Trial restrictions: no cryptocurrency mining; credit cannot pay for
  Gemini API in AI Studio.
- Trial ends → 30-day grace period → resources permanently deleted.

## Free Tier eligibility

- Active billing account (paid or free trial) in good standing.
- No negotiated pricing contract (except where the table says otherwise).
