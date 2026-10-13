---
type: reference
resource: https://docs.cloud.google.com/free/docs/free-cloud-features
sources:
  - https://docs.cloud.google.com/free/docs/free-cloud-features
  - https://docs.cloud.google.com/pricing/
verified: 2026-10-09
---

# Never Free Tier — veto list

Products with **no Free Tier** (or with conditions that silently bill).
Every entry is a Stage 3 veto: propose an alternative or stop.

| Resource | Why it bills | Free alternative |
|---|---|---|
| GPU / TPU on VMs | Always charged; blocked entirely during Free Trial | CPU-only machine types |
| Non-`e2-micro` VMs (n1/n2/e2-medium…) | Priced per vCPU-hour | `e2-micro` in `us-west1`/`us-central1`/`us-east1` |
| `e2-micro` outside the 3 US regions | No Free Tier outside `us-west1`/`us-central1`/`us-east1` | Move zone/region |
| Preemptible/Spot VMs | Not covered by Free Tier (hourly billing) | Non-preemptible `e2-micro` |
| SSD (`pd-ssd`) or balanced disks | Only **standard** disk has the 30 GB-month allowance | `--boot-disk-type=pd-standard` |
| Disks > 30 GB total standard | Overage billed per GB-month | Shrink to ≤ 30 GB |
| Cloud SQL / AlloyDB / Spanner / Bigtable / Memorystore | No Always Free tier (30-day trials only) | Firestore (free quotas) or SQLite on disk |
| Load balancers (external LB, forwarding rules) | Hourly + data charges | DNS-based routing / Cloud Run ingress |
| Static external IP **not attached** to a running resource | Charged while reserved/unused | Delete unused addresses |
| Cloud NAT, Cloud DNS zones beyond free ops, Cloud VPN | Per-hour/per-Gb charges | Avoid or verify pricing page first |
| Cloud Storage outside `us-east1`/`us-west1`/`us-central1` | Free Tier is region-locked | Create buckets in US regions |
| GKE node pools, clusters > 1, non-zonal clusters | Cluster fee + node compute billed | 1 zonal/Autopilot cluster; serverless alternatives |
| Anthos, Apigee, VMware Engine | Enterprise products, always billed | Not applicable |
| Vertex AI model-as-a-service / Gemini API via AI Studio | Not covered by $300 trial credit | Gemini API free tier (separate program) |
| Marketplace third-party images/instances | Usage billed outside Free Tier | First-party images only |
| Egress outside North America | Free egress allowances are NA-only | Keep traffic in NA |
| Cloud Logging beyond 50 GiB/project | Overage per GiB | Reduce log volume / exclusions |

## Usage-based limits (invisible to inventory audits)

These pass a resource audit but bill when usage crosses the monthly limit —
verify in **Cloud Billing reports** (grouped by SKU):

- Cloud Run requests / vCPU-seconds, Cloud Run functions invocations
- BigQuery query bytes, Cloud Storage Class A/B operations
- Pub/Sub message volume, Firestore reads/writes, API call counts
  (Vision, Natural Language, Video Intelligence)
- Cloud Build minutes beyond 2,500, log ingestion beyond 50 GiB
