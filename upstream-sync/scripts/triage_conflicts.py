# /// script
# requires-python = ">=3.9"
# ///
"""Triage conflicted files in a merge by repository-specific policy globs.

Run this while a merge is in progress with unmerged (conflicted) files.
Classifies each conflicted file as prefer-local, prefer-upstream,
whitespace-only, or needs-decision.

Exit codes:
  0  every conflicted file resolved or classified (none needs a human)
  1  one or more files remain 'needs-decision'
  2  error (not a repo, bad mode, git failure)
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import date


def log(msg):
    print(msg, file=sys.stderr)


def git(repo, *args, check=True):
    cmd = ["git", "-C", repo] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    return proc


def fail(msg):
    log(f"ERROR: {msg}")
    sys.exit(2)


def matches(path, pattern):
    """Match a repo-relative path against a glob.

    Supports plain globs (fnmatch on the full path) and directory
    prefixes: 'rules/**' and 'rules/*' both match 'rules/code/x.md',
    and 'rules/**' also matches files directly under rules/.
    """
    pattern = pattern.rstrip("/")
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.endswith("/**") and (
        path == pattern[:-3].rstrip("/") or path.startswith(pattern[:-2])
    ):
        return True
    if fnmatch.fnmatch(path, pattern + "/*") or fnmatch.fnmatch(path, pattern + "/**"):
        return True
    return False


def unmerged_files(repo):
    proc = git(repo, "diff", "--name-only", "--diff-filter=U", check=False)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def git_stage(repo, path, stage):
    proc = git(repo, "show", f":{stage}:{path}", check=False)
    return proc.stdout if proc.returncode == 0 else None


def whitespace_only(repo, path):
    """True when ours and theirs differ only in horizontal whitespace.

    Whitespace runs (spaces/tabs) collapse to a single space per line, so
    tab-vs-space and repeated-space edits classify as whitespace-only.
    The apply action keeps the whole 'ours' file, so indentation style is
    never broken by a partial merge.
    """
    ours = git_stage(repo, path, 2)
    theirs = git_stage(repo, path, 3)
    if ours is None or theirs is None:
        return False
    collapse = lambda text: [
        re.sub(r"[ \t]+", " ", ln).strip()
        for ln in text.splitlines()
        if ln.strip()
    ]
    return collapse(ours) == collapse(theirs)


def classify(repo, path, local_patterns, upstream_patterns):
    for p in local_patterns:
        if matches(path, p):
            return "prefer-local", f"matched --prefer-local '{p}'"
    for p in upstream_patterns:
        if matches(path, p):
            return "prefer-upstream", f"matched --prefer-upstream '{p}'"
    if whitespace_only(repo, path):
        return "whitespace-only", "ours and theirs differ only in whitespace"
    return "needs-decision", "no policy pattern matched"


def apply_decision(repo, path, decision):
    side = "--ours" if decision in ("prefer-local", "whitespace-only") else "--theirs"
    git(repo, "checkout", side, "--", path)
    git(repo, "add", "--", path)


def markdown_report(classification, resolved, unresolved, mode):
    lines = [
        f"# Conflict triage report — {date.today().isoformat()}",
        "",
        f"Mode: {mode}",
        "",
        "| File | Decision | Reason |",
        "|---|---|---|",
    ]
    for item in classification:
        lines.append(f"| {item['path']} | {item['decision']} | {item['reason']} |")
    lines.append("")
    lines.append(f"Resolved: {len(resolved)} | Unresolved: {len(unresolved)}")
    if unresolved:
        lines.append("")
        lines.append("## Needs manual decision")
        for path in unresolved:
            lines.append(f"- {path}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Classify (and optionally resolve) merge conflicts by policy globs.",
        epilog="Run while a merge is in progress. Exit 0: fully classified | 1: decisions pending | 2: error.",
    )
    parser.add_argument("--repo", default=".", help="path to the local repository (default: .)")
    parser.add_argument(
        "--prefer-local", action="append", default=[], metavar="GLOB",
        help="glob for files that should keep the local (ours) version; repeatable",
    )
    parser.add_argument(
        "--prefer-upstream", action="append", default=[], metavar="GLOB",
        help="glob for files that should take the upstream (theirs) version; repeatable",
    )
    parser.add_argument(
        "--mode", choices=["preview", "apply"], default="preview",
        help="preview: report only (default); apply: resolve matching files with git checkout/add",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON to stdout")
    parser.add_argument("--report", metavar="PATH", help="also write a markdown report to PATH")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if git(repo, "rev-parse", "--git-dir", check=False).returncode != 0:
        fail(f"'{args.repo}' is not a git repository")

    files = unmerged_files(repo)
    if not files:
        result = {"conflicted": 0, "classification": [], "resolved": [], "unresolved": [], "mode": args.mode}
        if args.json:
            json.dump(result, sys.stdout, indent=2)
            print()
        else:
            print("No conflicted files.")
        sys.exit(0)

    classification, resolved, unresolved = [], [], []
    for path in files:
        decision, reason = classify(repo, path, args.prefer_local, args.prefer_upstream)
        if decision == "whitespace-only":
            reason += "; resolving as prefer-local"
        item = {"path": path, "decision": decision, "reason": reason}
        classification.append(item)
        if decision == "needs-decision":
            unresolved.append(path)
            continue
        if args.mode == "apply":
            try:
                apply_decision(repo, path, decision)
                item["applied"] = True
            except RuntimeError as exc:
                item["applied"] = False
                item["error"] = str(exc)
                unresolved.append(path)
                continue
            resolved.append(path)
            log(f"Resolved {path} -> {decision}")
        else:
            resolved.append(path)
            log(f"Preview: {path} -> {decision}")

    if args.mode == "preview":
        unresolved = [i["path"] for i in classification if i["decision"] == "needs-decision"]
        resolved = [i["path"] for i in classification if i["decision"] != "needs-decision"]

    result = {
        "conflicted": len(files),
        "classification": classification,
        "resolved": resolved,
        "unresolved": unresolved,
        "mode": args.mode,
    }
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()

    if not args.json:
        print(markdown_report(classification, resolved, unresolved, args.mode))

    if args.report:
        report_path = os.path.abspath(args.report)
        os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
        with open(report_path, "w") as fh:
            fh.write(markdown_report(classification, resolved, unresolved, args.mode))
        log(f"Wrote report to {report_path}")

    sys.exit(1 if unresolved else 0)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        fail(str(exc))
