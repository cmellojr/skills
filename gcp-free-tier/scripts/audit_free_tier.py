#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Audit a Google Cloud project against Free Tier structural limits.

Read-only. Requires the gcloud CLI on PATH and authenticated credentials
(`gcloud auth login`). Emits JSON to stdout (or text with --format=text).

Exit codes:
  0  no violations
  1  violations found
  2  tooling/auth/project error (audit incomplete)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from calendar import monthrange

FREE_REGIONS = {"us-west1", "us-central1", "us-east1"}
FREE_MACHINE = "e2-micro"
FREE_DISK_TYPE = "pd-standard"
FREE_DISK_TOTAL_GB = 30
GUARDRAIL_BUDGET_NAME = "gcp-free-tier-guardrail"
LIMITS_SNAPSHOT = "references/free-tier-limits.md (verified 2026-10-09)"

violations: list[dict] = []
warnings: list[dict] = []
skipped: list[dict] = []


def add(bucket: list, rule: str, resource: str, detail: str, fix: str) -> None:
    bucket.append(
        {"rule": rule, "severity": "violation" if bucket is violations else "warning",
         "resource": resource, "detail": detail, "fix": fix}
    )


def gcloud(args: list[str], project: str | None = None):
    """Run a gcloud command requesting JSON. Returns (data, error)."""
    cmd = ["gcloud", *args]
    if not any(a == "--format" or a.startswith("--format=") for a in args):
        cmd += ["--format=json"]
    if project and "--project" not in args and not args[:2] == ["projects", "describe"]:
        cmd += ["--project", project]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return None, "gcloud CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return None, f"timeout running: {' '.join(cmd)}"
    if proc.returncode != 0:
        return None, proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown gcloud error"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError:
        return None, "gcloud returned non-JSON output"


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def region_of(zone_or_url: str) -> str:
    zone = zone_or_url.rstrip("/").split("/")[-1]
    return zone.rsplit("-", 1)[0]


def base_of(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def check_instances(project: str) -> list[dict]:
    data, err = gcloud(
        ["compute", "instances", "list",
         "--format=json(name,zone,status,machineType,scheduling,guestAccelerators,disks,creationTimestamp,lastStartTimestamp)"],
        project,
    )
    if err:
        skipped.append({"check": "vm-instances", "reason": err})
        return []
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    hours_in_month = monthrange(now.year, now.month)[1] * 24
    est_hours = 0.0

    for vm in data or []:
        name = vm.get("name", "?")
        zone = vm.get("zone", "")
        status = vm.get("status", "")
        running = status == "RUNNING"
        mtype = base_of(vm.get("machineType", ""))
        region = region_of(zone)

        if mtype != FREE_MACHINE:
            if running:
                add(violations, "vm-machine-type", name,
                    f"machine type {mtype} is not Free Tier",
                    f"recreate as {FREE_MACHINE} in {sorted(FREE_REGIONS)[0]}")
            else:
                add(warnings, "vm-machine-type", name,
                    f"machine type {mtype} not Free Tier (currently {status})",
                    f"delete it, or recreate as {FREE_MACHINE} before starting")
        if region not in FREE_REGIONS:
            if running:
                add(violations, "vm-region", name,
                    f"region {region} is outside Free Tier regions {sorted(FREE_REGIONS)}",
                    f"recreate in one of {sorted(FREE_REGIONS)}")
            else:
                add(warnings, "vm-region", name,
                    f"region {region} outside Free Tier regions (currently {status})",
                    f"recreate in one of {sorted(FREE_REGIONS)}")
        if vm.get("guestAccelerators"):
            add(violations, "vm-gpu", name,
                f"attached accelerators {[base_of(a.get('type', '')) for a in vm['guestAccelerators']]} are always billed",
                "remove all GPUs/TPUs")
        sched = vm.get("scheduling") or {}
        if sched.get("preemptible") or sched.get("spot") or sched.get("provisioningModel") == "SPOT":
            if running:
                add(violations, "vm-preemptible", name,
                    "preemptible/spot VMs are not Free Tier",
                    f"recreate as a non-preemptible {FREE_MACHINE}")
        for d in vm.get("disks") or []:
            for init in d.get("initializeParams", {}).get("diskType", "") and [d["initializeParams"]] or []:
                if base_of(init.get("diskType", FREE_DISK_TYPE)) != FREE_DISK_TYPE:
                    add(violations, "vm-disk-type", name,
                        f"boot disk type {base_of(init['diskType'])} is billed (Free Tier covers pd-standard only)",
                        "recreate with --boot-disk-type=pd-standard")

        if running and mtype == FREE_MACHINE and region in FREE_REGIONS:
            start = parse_ts(vm.get("lastStartTimestamp")) or parse_ts(vm.get("creationTimestamp"))
            if start:
                start = max(start, month_start)
                est_hours += max(0.0, (now - start).total_seconds() / 3600)

    if est_hours > hours_in_month:
        add(warnings, "vm-hours-estimate", "e2-micro fleet",
            f"estimated {est_hours:.0f} instance-hours this month > {hours_in_month}h Free Tier budget "
            "(estimate assumes continuous running since last start)",
            "reduce concurrent e2-micro runtime; the limit is hours, not instance count")
    return data or []


def check_disks(project: str) -> None:
    data, err = gcloud(["compute", "disks", "list",
                        "--format=json(name,sizeGb,type,zone)"], project)
    if err:
        skipped.append({"check": "disks", "reason": err})
        return
    std_gb = 0
    for disk in data or []:
        dtype = base_of(disk.get("type", FREE_DISK_TYPE))
        size = int(disk.get("sizeGb", 0))
        if dtype != FREE_DISK_TYPE:
            add(violations, "disk-type", disk.get("name", "?"),
                f"{dtype} disk ({size} GB) is billed; Free Tier covers pd-standard only",
                "recreate the disk as pd-standard (snapshot + recreate)")
        else:
            std_gb += size
    if std_gb > FREE_DISK_TOTAL_GB:
        add(violations, "disk-total-size", "all pd-standard disks",
            f"{std_gb} GB total exceeds {FREE_DISK_TOTAL_GB} GB-months Free Tier",
            f"delete or shrink disks to <= {FREE_DISK_TOTAL_GB} GB total")


def check_buckets(project: str) -> None:
    data, err = gcloud(["storage", "buckets", "list", "--format=json(name,location)"], project)
    if err:
        skipped.append({"check": "buckets", "reason": err})
        return
    for b in data or []:
        loc = str(b.get("location", "")).upper()
        name = b.get("name", "?")
        if loc in {r.upper() for r in FREE_REGIONS}:
            continue
        if loc == "US":
            add(warnings, "bucket-region", name,
                "US multi-region bucket; Free Tier is specified for us-east1/us-west1/us-central1 regional storage",
                "verify eligibility or recreate the bucket in us-central1")
        else:
            add(violations, "bucket-region", name,
                f"bucket location {loc} is outside Free Tier regions {sorted(FREE_REGIONS)}",
                f"recreate the bucket in one of {sorted(FREE_REGIONS)}")


def check_sql(project: str) -> None:
    data, err = gcloud(["sql", "instances", "list", "--format=json(name,state)"], project)
    if err:
        skipped.append({"check": "cloud-sql", "reason": err})
        return
    for inst in data or []:
        add(violations, "sql-instance", inst.get("name", "?"),
            "Cloud SQL has no Always Free tier (30-day trial only); billed while it exists",
            "delete it; use Firestore free quotas or SQLite instead")


def check_gke(project: str) -> None:
    data, err = gcloud(["container", "clusters", "list", "--format=json(name,status,location)"], project)
    if err:
        skipped.append({"check": "gke", "reason": err})
        return
    clusters = data or []
    if len(clusters) > 1:
        add(violations, "gke-cluster-count", f"{len(clusters)} clusters",
            "Free Tier covers one Autopilot or zonal Standard cluster only",
            "delete all but one zonal cluster")
    elif len(clusters) == 1:
        c = clusters[0]
        add(warnings, "gke-cluster-scope", c.get("name", "?"),
            "cluster fee is free, but node compute/networking/storage are billed",
            "verify node pools are scaled to zero or use serverless alternatives")


def check_forwarding_rules(project: str) -> None:
    data, err = gcloud(["compute", "forwarding-rules", "list", "--format=json(name)"], project)
    if err:
        skipped.append({"check": "load-balancers", "reason": err})
        return
    for fr in data or []:
        add(violations, "load-balancer", fr.get("name", "?"),
            "load balancers charge hourly plus data processing",
            "delete it; use Cloud Run ingress or DNS routing")


def check_addresses(project: str) -> None:
    data, err = gcloud(["compute", "addresses", "list",
                        "--format=json(name,status,type,users)"], project)
    if err:
        skipped.append({"check": "static-ips", "reason": err})
        return
    for addr in data or []:
        name = addr.get("name", "?")
        if addr.get("users"):
            add(warnings, "static-ip", name,
                "attached static IP may incur hourly charges on top of Free Tier",
                "prefer an ephemeral external IP and release the static one")
        else:
            add(violations, "static-ip", name,
                "unused static IP address is billed while reserved",
                "delete the address")


def check_budget(billing_account: str, project: str | None) -> None:
    data, err = gcloud(["billing", "budgets", "list",
                        "--billing-account", billing_account,
                        "--format=json(displayName)"])
    if err:
        skipped.append({"check": "budget", "reason": err})
        return
    names = {b.get("displayName", "") for b in data or []}
    if GUARDRAIL_BUDGET_NAME in names:
        return
    scope = f" for project {project}" if project else ""
    add(warnings, "budget-missing", billing_account,
        f"no '{GUARDRAIL_BUDGET_NAME}' budget alert{scope}",
        "run: bash scripts/setup_guardrails.sh --billing-account <id> --project <id> --apply")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a Google Cloud project against Free Tier structural limits.",
        epilog="Example: uv run scripts/audit_free_tier.py --project my-project --billing-account 012345-6789AB-CDEF01",
    )
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT")
                        or os.environ.get("GCP_PROJECT"),
                        help="project ID (or GOOGLE_CLOUD_PROJECT env)")
    parser.add_argument("--billing-account", help="billing account ID for the budget check")
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="output format (default: json)")
    parser.add_argument("--skip-budget", action="store_true",
                        help="skip the budget alert check even if --billing-account is set")
    args = parser.parse_args()

    if not args.project:
        print("error: --project is required (or set GOOGLE_CLOUD_PROJECT)", file=sys.stderr)
        return 2
    if not shutil.which("gcloud"):
        print("error: gcloud CLI not found. Install: https://docs.cloud.google.com/sdk/docs/install-sdk",
              file=sys.stderr)
        return 2

    _, err = gcloud(["projects", "describe", args.project])
    if err:
        print(f"error: cannot access project '{args.project}': {err}\n"
              "fix: run `gcloud auth login` and verify the project ID and permissions",
              file=sys.stderr)
        return 2

    check_instances(args.project)
    check_disks(args.project)
    check_buckets(args.project)
    check_sql(args.project)
    check_gke(args.project)
    check_forwarding_rules(args.project)
    check_addresses(args.project)
    if args.billing_account and not args.skip_budget:
        check_budget(args.billing_account, args.project)

    report = {
        "project": args.project,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "limits_source": LIMITS_SNAPSHOT,
        "violations": violations,
        "warnings": warnings,
        "checks_skipped": skipped,
        "summary": {
            "violations": len(violations),
            "warnings": len(warnings),
            "checks_skipped": len(skipped),
        },
    }

    if args.format == "json":
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        for item in violations + warnings:
            print(f"[{item['severity']}] {item['rule']}: {item['resource']} — {item['detail']}\n"
                  f"    fix: {item['fix']}")
        for item in skipped:
            print(f"[skipped] {item['check']}: {item['reason']}")
        print(f"summary: {len(violations)} violation(s), {len(warnings)} warning(s), "
              f"{len(skipped)} skipped check(s)")

    if skipped:
        print("note: skipped checks mean the audit is incomplete — never treat them as passes",
              file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
