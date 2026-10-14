# /// script
# requires-python = ">=3.9"
# ///
"""Check whether a fork's upstream has new commits and preview merge conflicts.

Exit codes:
  0  up to date (upstream has no commits missing locally)
  1  updates available (behind upstream)
  2  error (bad repo, missing remote, fetch failure)
"""

import argparse
import json
import os
import re
import subprocess
import sys


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


def fail(msg, code=2):
    log(f"ERROR: {msg}")
    sys.exit(code)


def is_commit_sha(ref):
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", ref))


def resolve_upstream(repo, upstream_arg, branch_arg):
    """Return (remote_name, remote_url, branch, ref) for the upstream side."""
    remotes = {
        line.split()[0]: line.split()[1]
        for line in git(repo, "remote", "-v").stdout.splitlines()
        if line.split()
    }
    if not remotes:
        fail("no git remotes configured; add one with: git remote add upstream <url>")

    if upstream_arg and "/" in upstream_arg and not upstream_arg.startswith("http"):
        # owner/repo shorthand -> github URL, added as remote if missing
        url = f"https://github.com/{upstream_arg}.git"
        remote = "upstream"
        if remotes.get(remote) != url:
            git(repo, "remote", "add", remote, url)
            remotes[remote] = url
    elif upstream_arg:
        if upstream_arg not in remotes:
            fail(f"remote '{upstream_arg}' not found; known remotes: {', '.join(remotes)}")
        remote = upstream_arg
        url = remotes[remote]
    elif "upstream" in remotes:
        remote = "upstream"
        url = remotes[remote]
    else:
        fail(
            "no remote named 'upstream'; pass --upstream <remote> or "
            "--upstream owner/repo (known remotes: " + ", ".join(remotes) + ")"
        )

    if branch_arg:
        branch = branch_arg
    else:
        head = git(repo, "symbolic-ref", f"refs/remotes/{remote}/HEAD", check=False)
        if head.returncode == 0 and head.stdout.strip():
            branch = head.stdout.strip().rsplit("/", 1)[-1]
        else:
            for candidate in ("main", "master"):
                if git(repo, "rev-parse", "--verify", f"{remote}/{candidate}", check=False).returncode == 0:
                    branch = candidate
                    break
            else:
                branch = "main"
    return remote, url, branch, f"{remote}/{branch}"


def preview_conflicts_new(repo, head, ref):
    """git >= 2.38: merge-tree --write-tree --name-only. Returns (files, method)."""
    proc = git(repo, "merge-tree", "--write-tree", "--name-only", head, ref, check=False)
    if proc.returncode == 0:
        return [], "merge-tree-write-tree"
    if proc.returncode == 1:
        # stdout: tree-oid, conflicted file names, blank line, info messages
        lines = proc.stdout.splitlines()
        files = []
        for ln in lines[1:]:
            if not ln.strip():
                break
            files.append(ln.strip())
        return files, "merge-tree-write-tree"
    return None, f"merge-tree-write-tree-failed: {proc.stderr.strip()}"


def preview_conflicts_legacy(repo, head, ref):
    """git < 2.38: legacy merge-tree <base> <ours> <theirs>. Returns (files, method)."""
    base = git(repo, "merge-base", head, ref).stdout.strip()
    proc = git(repo, "merge-tree", base, head, ref, check=False)
    files = set()
    for line in proc.stdout.splitlines():
        m = re.match(r"\s+(our|their)\s+\d+\s+[0-9a-f]+\s+(.+)$", line)
        if m:
            files.add(m.group(2).strip())
    return sorted(files), "merge-tree-legacy"


def main():
    parser = argparse.ArgumentParser(
        description="Check a fork for new upstream commits and preview merge conflicts.",
        epilog="Exit 0: up to date | 1: updates available | 2: error.",
    )
    parser.add_argument("--repo", default=".", help="path to the local repository (default: .)")
    parser.add_argument(
        "--upstream",
        help="upstream remote name (e.g. 'upstream') or owner/repo GitHub shorthand (default: remote named 'upstream')",
    )
    parser.add_argument("--branch", help="upstream branch (default: upstream HEAD, else main/master)")
    parser.add_argument("--no-fetch", action="store_true", help="skip 'git fetch' and use cached refs")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON to stdout")
    parser.add_argument("--max-commits", type=int, default=100, help="cap commits listed in output (default: 100)")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if git(repo, "rev-parse", "--git-dir", check=False).returncode != 0:
        fail(f"'{args.repo}' is not a git repository")

    head_proc = git(repo, "rev-parse", "HEAD", check=False)
    if head_proc.returncode != 0:
        fail("repository has no commits yet")
    head = head_proc.stdout.strip()

    remote, url, branch, ref = resolve_upstream(repo, args.upstream, args.branch)

    fetched = False
    if not args.no_fetch:
        log(f"Fetching {remote} ...")
        if git(repo, "fetch", remote, "--prune", check=False).returncode != 0:
            fail(f"git fetch {remote} failed (check network and credentials)")
        fetched = True

    if git(repo, "rev-parse", "--verify", ref, check=False).returncode != 0:
        fail(f"ref '{ref}' not found after fetch; pass --branch <name>")

    counts = git(repo, "rev-list", "--left-right", "--count", f"HEAD...{ref}").stdout.split()
    ahead, behind = int(counts[0]), int(counts[1])

    new_commits, changed_files, conflicts = [], [], {}
    if behind > 0:
        log_proc = git(repo, "log", "--oneline", f"HEAD..{ref}", f"-{args.max_commits}")
        for line in log_proc.stdout.splitlines():
            sha, _, subject = line.partition(" ")
            new_commits.append({"sha": sha, "subject": subject})
        diff = git(repo, "diff", "--name-status", f"HEAD...{ref}").stdout.splitlines()
        for line in diff:
            parts = line.split("\t")
            if len(parts) >= 2:
                changed_files.append({"status": parts[0], "path": parts[-1]})
        files, method = preview_conflicts_new(repo, head, ref)
        if files is None:
            files, method = preview_conflicts_legacy(repo, head, ref)
        conflicts = {"previewed": True, "method": method, "files": files}

    result = {
        "repo": repo,
        "upstream": {"remote": remote, "url": url, "branch": branch, "ref": ref},
        "head": head,
        "fetched": fetched,
        "up_to_date": behind == 0,
        "ahead": ahead,
        "behind": behind,
        "new_commits": new_commits,
        "changed_files": changed_files,
        "conflicts": conflicts if behind > 0 else {"previewed": False, "method": None, "files": []},
    }

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()

    if not args.json:
        if behind == 0:
            print(f"Up to date with {ref} (ahead {ahead}).")
        else:
            print(f"Behind {ref} by {behind} commit(s); local ahead by {ahead}.")
            print(f"New commits (up to {args.max_commits}):")
            for c in new_commits:
                print(f"  {c['sha']} {c['subject']}")
            print(f"Changed files: {len(changed_files)}")
            if conflicts.get("files"):
                print(f"Predicted conflict files ({conflicts['method']}):")
                for f in conflicts["files"]:
                    print(f"  {f}")
            else:
                print("No conflicts predicted; merge should be clean.")

    sys.exit(0 if behind == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        fail(str(exc))
