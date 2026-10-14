---
name: upstream-sync
description: >
  Workflow to keep a fork aligned with its upstream repository in any Git
  project. Detects new upstream commits, previews merge conflicts, discovers
  resolution policies in the target repository (prefer-local paths, commit
  rules, validations), and executes a reviewed merge plan preserving
  fork-owned changes. Verifies zero conflict markers and runs the
  repository's own checks before committing. Activate when the user asks if
  a fork's upstream was updated, requests merging upstream changes, or needs
  conflicts resolved by local repository policies.
license: Apache-2.0
metadata:
  category: devops
  tags: "git, fork, merge, conflict-resolution, workflow"
  author: Carlos Mello Jr (cmellojr@gmail.com)
  version: "1.0.0"
  canonical: https://github.com/cmellojr/skills/tree/main/upstream-sync/
compatibility: Requires git (2.38+ recommended for accurate conflict preview; older versions fall back to legacy merge-tree)
---

# Upstream Sync for Forks

Keep a fork in sync with its upstream repository: detect new upstream
commits, plan the merge from the repository's own resolution policies, then
execute and verify. The skill never pushes or opens PRs without explicit
user approval — merges stay local until the user says otherwise.

Works in any Git repository that tracks an upstream remote. When no
`upstream` remote exists, it can be added from an `owner/repo` shorthand.

## Available scripts

- `scripts/check_upstream.py` — fetches the upstream remote, reports commits
  behind/ahead, changed files, and predicted conflict files. JSON with
  `--json`; exit `0` up to date, `1` updates available, `2` error.
- `scripts/triage_conflicts.py` — classifies conflicted files during a merge
  as prefer-local / prefer-upstream / whitespace-only / needs-decision from
  policy globs; optionally resolves them. Exit `0` fully classified,
  `1` decisions pending, `2` error.

```bash
# 1. Is upstream ahead? (exit 1 = updates available)
uv run scripts/check_upstream.py --repo /path/to/fork --json

# 2. Point at a specific remote or branch
uv run scripts/check_upstream.py --repo . --upstream owner/repo --branch main

# 3. Classify conflicts while a merge is in progress (report only)
uv run scripts/triage_conflicts.py --repo . \
  --prefer-local 'AGENTS.md' --prefer-local 'rules/**' --json

# 4. Apply the policy decisions, leaving needs-decision files untouched
uv run scripts/triage_conflicts.py --repo . \
  --prefer-local 'AGENTS.md' --prefer-local 'rules/**' --mode apply \
  --report .sync/triage-report.md
```

If `uv` is unavailable, run with plain `python3` (stdlib only).

## Workflow

### Stage 1 — Check for upstream updates

1. Run `uv run scripts/check_upstream.py --repo <path> --json`.
2. Exit `0` — report "up to date" (include ahead count) and stop.
3. Exit `1` — report new commits and predicted conflicts; continue to Stage 2.
4. Exit `2` — fix tooling first: not a git repo, missing `upstream` remote
   (`git remote add upstream <url>` or rerun with `--upstream owner/repo`),
   or fetch/auth failure. Do not proceed on errors.
5. If the working tree is dirty (`git status --porcelain`), ask the user to
   commit or stash first. Never merge on a dirty tree.

### Stage 2 — Discover local resolution policies

Read `references/policy-discovery.md` and extract, in priority order:

- [ ] Prefer-local paths (fork-owned files) and prefer-upstream paths
- [ ] Commit message and branch rules (e.g. `rules/git.md`)
- [ ] Mandatory validations (tests, linters, `--check` scripts, CI workflows)
- [ ] Post-merge obligations (e.g. mirroring framework files into a nested
      `.agents/` clone)
- [ ] Red lines — files or content that must survive the merge

Record every finding with its source file. If the repository is silent, use
the documented defaults and state that in the plan.

### Stage 3 — Conflict triage and merge plan

1. Run the triage in preview mode against the predicted conflict set:

   ```bash
   uv run scripts/triage_conflicts.py --repo <path> \
     --prefer-local <glob> --prefer-local <glob> ... \
     --prefer-upstream <glob> ... --json
   ```

2. Categorize every conflicted file: `prefer-local`, `prefer-upstream`,
   `whitespace-only` (resolved as prefer-local), or `needs-decision`.
3. For each `needs-decision` file, inspect both sides
   (`git show :2:<path>` ours, `git show :3:<path>` theirs) and form an
   explicit per-file decision.
4. Write a phased merge plan using `references/merge-plan-template.md` and
   present it to the user. **Do not start the merge until the plan is
   approved** (Plan-Validate-Execute).

### Stage 4 — Execute the merge

1. Create a sync branch from the target branch:

   ```bash
   git checkout -b sync/upstream-<branch>-<YYYYMMDD> <target-branch>
   ```

2. Merge without fast-forward so the integration is one reviewable commit:

   ```bash
   git merge --no-ff upstream/<branch>
   ```

   If git refuses due to unrelated histories and the plan approved it, rerun
   with `--allow-unrelated-histories`.

3. Apply policy decisions:

   ```bash
   uv run scripts/triage_conflicts.py --repo <path> \
     --prefer-local <glob> ... --prefer-upstream <glob> ... \
     --mode apply --report .sync/triage-report-<YYYYMMDD>.md
   ```

4. Resolve remaining `needs-decision` files by hand per the approved plan,
   then `git add` each one.
5. Verify no conflict markers survive anywhere:

   ```bash
   git diff --check
   git grep -nE '^(<{7}|={7}|>{7})( |$)' -- . || true
   ```

6. Finalize with `git commit` (the merge message opens the editor; keep the
   repository's commit style). Never `--amend` a merge that may already be
   shared.

### Stage 5 — Validate

1. Run every validation discovered in Stage 2 (unit tests, linters,
   markdown checks, drift checks such as `sync-framework.sh --check`).
2. Confirm the tree is clean (`git status --porcelain` is empty apart from
   intentionally untracked files).
3. On any failure: fix forward on the sync branch and rerun; if the merge
   itself is wrong, `git merge --abort` (while conflicted) or
   `git reset --hard <target-branch>` (after a bad merge commit) and revise
   the plan.

### Stage 6 — Commit and report

1. Confirm the commit message follows the repository's rules (Google style
   by default: subject <= 50 chars, imperative mood, body wrapped at 72
   explaining what/why).
2. Build the sync report:

   ```markdown
   # Upstream sync — <fork> — <date>
   - Branch: sync/upstream-<branch>-<YYYYMMDD> (local)
   - Upstream: <remote>/<branch>, <N> commits merged
   - Conflicts: <total> (policy-resolved <n>, manual <n>)
   - Validations: <commands run> — PASS|FAIL
   ```

3. **Ask before pushing.** Offer, do not run:

   ```bash
   git push -u origin sync/upstream-<branch>-<YYYYMMDD>
   gh pr create --base <target-branch> --head sync/upstream-<branch>-<YYYYMMDD> \
     --title "chore: sync from <upstream-owner>/<repo>" --draft
   ```

## Policy decision framework

| Situation | Decision |
|---|---|
| File matches a prefer-local pattern | Keep ours (`git checkout --ours`) |
| File matches a prefer-upstream pattern | Take theirs (`git checkout --theirs`) |
| Ours and theirs differ only in whitespace/formatting | Keep ours |
| Fork never modified the file since forking | Take theirs |
| Changelog-type file (`CHANGELOG.md`) | Merge both timelines |
| Fork added content inside an upstream-owned file | Take upstream's structure, re-insert the fork's additions explicitly |
| Anything ambiguous | `needs-decision` — show both sides to the user, never guess |

## Gotchas & edge cases

- **Shallow clones** (`--depth=1` remotes): `git fetch --unshallow` the
  upstream remote if `merge-base` or `rev-list` fails or reports nonsense.
- **No upstream remote**: add it (`git remote add upstream <url>`) or pass
  `--upstream owner/repo`; `origin` alone is not an upstream.
- **Default branch mismatch**: if the fork's target branch and the
  upstream's default branch differ, always name both explicitly
  (`--branch` for upstream; checkout base for the sync branch).
- **Unrelated histories**: common on the very first sync; only enable
  `--allow-unrelated-histories` when the plan says so.
- **Nested framework clones** (e.g. a root repo mirrored in `.agents/`):
  after merging, run the repo's drift check and resync; a merge that updates
  only one side leaves the copies diverged.
- **Files deleted upstream but patched locally**: the merge reports a
  modify/delete conflict — default to keeping the local file and note it in
  the plan.
- **Legacy `merge-tree`**: on git older than 2.38 the conflict preview is
  best-effort; treat an empty predicted list as "unknown", not "clean", and
  rely on the real merge for the authoritative conflict set.

## Failure recovery

- **Merge conflicts mid-flight, plan is wrong**: `git merge --abort` to
  return to the pre-merge state; revise the plan before retrying.
- **Bad merge already committed**: `git reset --hard <target-branch>` on the
  sync branch (never on a pushed shared branch without user approval).
- **Rebase accidentally started**: `git rebase --abort`.
- **Fetch fails**: verify network and credentials
  (`git ls-remote upstream` to test); rerun with `--no-fetch` only to
  inspect already-fetched state, clearly labeled as stale.
- **Wrong branch checked out**: return with `git checkout <previous-branch>`;
  never resolve conflicts on `main`/`develop` directly.
- **Triage script exits 2**: it refused to act (not a repo, git failure) —
  read the stderr message; do not force paths it did not accept.
