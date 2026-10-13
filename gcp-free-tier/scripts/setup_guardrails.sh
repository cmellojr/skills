#!/usr/bin/env bash
# Create Cloud Billing budget alerts (50/90/100%) and show compute quotas.
# Dry-run by default; pass --apply to make changes. Idempotent.
set -euo pipefail

BILLING_ACCOUNT=""
PROJECT=""
AMOUNT="1"
DISPLAY_NAME="gcp-free-tier-guardrail"
APPLY=0

usage() {
  cat <<'EOF'
Usage: bash scripts/setup_guardrails.sh --billing-account ID [options]

Options:
  --billing-account ID   Billing account ID (required, e.g. 012345-6789AB-CDEF01)
  --project ID           Scope the budget to one project (recommended)
  --amount N             Budget amount in USD (default: 1)
  --name NAME            Budget display name (default: gcp-free-tier-guardrail)
  --apply                Execute instead of printing the commands (dry-run)
  -h, --help             Show this help

Creates a budget alert with 50%/90%/100% thresholds (email to billing
account IAM users) and prints compute quota usage.

NOTE: budget alerts only send notifications — they never stop resources.
See references/guardrails.md for the escalation ladder.

Examples:
  bash scripts/setup_guardrails.sh --billing-account 012345-6789AB-CDEF01 --project my-project
  bash scripts/setup_guardrails.sh --billing-account 012345-6789AB-CDEF01 --project my-project --apply
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --billing-account) BILLING_ACCOUNT="${2:?missing value for --billing-account}"; shift 2 ;;
    --project)         PROJECT="${2:?missing value for --project}"; shift 2 ;;
    --amount)          AMOUNT="${2:?missing value for --amount}"; shift 2 ;;
    --name)            DISPLAY_NAME="${2:?missing value for --name}"; shift 2 ;;
    --apply)           APPLY=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    *) echo "error: unknown option '$1' (see --help)" >&2; exit 2 ;;
  esac
done

if [[ -z "$BILLING_ACCOUNT" ]]; then
  echo "error: --billing-account is required (see --help)" >&2
  exit 2
fi
if ! command -v gcloud >/dev/null 2>&1; then
  echo "error: gcloud CLI not found. Install: https://docs.cloud.google.com/sdk/docs/install-sdk" >&2
  exit 2
fi

CREATE=(gcloud billing budgets create
  --billing-account="$BILLING_ACCOUNT"
  --display-name="$DISPLAY_NAME"
  --budget-amount="${AMOUNT}USD"
  --calendar-period=month
  --threshold-rule=percent=0.50
  --threshold-rule=percent=0.90
  --threshold-rule=percent=1.00)
if [[ -n "$PROJECT" ]]; then
  CREATE+=(--filter-projects="projects/$PROJECT")
fi

ENABLE=(gcloud services enable billingbudgets.googleapis.com)
QUOTAS=(gcloud compute project-info describe --project="$PROJECT" --format="value(quotas)")

run() {
  if [[ "$APPLY" -eq 1 ]]; then
    echo "+ $*" >&2
    "$@"
  else
    echo "DRY-RUN: $*"
  fi
}

# 1. Enable the Budgets API (idempotent)
run "${ENABLE[@]}"

# 2. Create the budget only if it does not exist yet
if [[ "$APPLY" -eq 1 ]]; then
  existing="$(gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" \
    --format='value(displayName)' 2>/dev/null || true)"
  if grep -Fxq "$DISPLAY_NAME" <<<"$existing"; then
    echo "budget '$DISPLAY_NAME' already exists — skipping creation" >&2
  else
    "${CREATE[@]}"
    echo "budget '$DISPLAY_NAME' created (${AMOUNT} USD, thresholds 50/90/100%)" >&2
  fi
else
  run "${CREATE[@]}"
fi

# 3. Quota overview
if [[ -n "$PROJECT" ]]; then
  if [[ "$APPLY" -eq 1 ]]; then
    echo "--- compute quotas (CPUS, DISKS_TOTAL_GB, IN_USE_ADDRESSES) for $PROJECT ---"
    gcloud compute project-info describe --project="$PROJECT" \
      --format="value(quotas)" 2>/dev/null \
      | tr ',' '\n' | grep -E 'CPUS|DISKS_TOTAL_GB|IN_USE_ADDRESSES' || true
  else
    run "${QUOTAS[@]}"
  fi
else
  echo "note: --project not set; skipping project quota overview and budget scope" >&2
fi

if [[ "$APPLY" -eq 0 ]]; then
  echo "dry-run only — re-run with --apply to execute"
fi
