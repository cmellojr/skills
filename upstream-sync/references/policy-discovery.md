---
type: reference
resource: policy-discovery
---

# Policy discovery in the target repository

Every repository that maintains a fork encodes (explicitly or implicitly) how
upstream changes should be integrated. Discover these policies before
resolving any conflict — never guess.

## Priority of policy sources

Search in this order; the first source that speaks on a topic wins.

1. **Dedicated sync tooling** — scripts under `sync-keeper/`, `scripts/*sync*`,
   or a `Makefile` target mentioning `upstream`/`sync`. These usually contain
   hard-coded prefer-local/prefer-upstream path patterns.
2. **Agent instruction files** — `AGENTS.md`, `.agents/AGENTS.md`,
   `ENTRYPOINT.md`, `.context.md`. Look for operational checklists that name
   mandatory validations or files that must never be overwritten.
3. **Rules and contributing docs** — `rules/`, `docs/CONTRIBUTING.md`,
   `docs/` governance notes, `.github/` review rules. Commit message style,
   branch naming, and review requirements live here.
4. **Git history** — `git log --merges --oneline`, then
   `git show <merge-commit>` for past upstream merges. Precedent is policy:
   if every past sync kept `rules/**` local, keep doing that.
5. **Placeholder** — if nothing is found, apply the defaults below and say so
   in the plan.

## What to extract

| Question | Where to look | Example finding |
|---|---|---|
| Which paths are fork-owned (prefer local)? | sync scripts, AGENTS.md, past merges | `AGENTS.md`, `rules/**`, `skills/**`, `personas/**` |
| Which paths track upstream (prefer theirs)? | sync scripts, past merges | files the fork never customized |
| Commit message rules? | `rules/git.md`, CONTRIBUTING | subject <= 50 chars, imperative, body wrapped at 72 |
| Mandatory validations? | AGENTS.md, CI workflows in `.github/workflows/` | unit tests, markdown linters, `--check` scripts |
| Post-merge sync obligations? | scripts such as `sync-framework.sh` | mirror framework files into a nested `.agents/` clone |
| Anything that must not change? | red lines in AGENTS.md or rules | rebranding, local doc structure, added rule files |

## Default policies (only when the repository is silent)

- Prefer **local** for files the fork added or owns: instruction files
  (`AGENTS.md`), rules, skills, personas, docs, CI workflows.
- Prefer **upstream** for files the fork never modified after forking.
- **Merge both** timelines for changelogs (`CHANGELOG.md`).
- Anything else: `needs-decision` — present the conflict to the user.

## Recording the findings

Write a short "Discovered policies" section into the merge plan (see
[merge-plan-template.md](merge-plan-template.md)) with one line per finding
and its source file. Pass the prefer-local/prefer-upstream paths to
`scripts/triage_conflicts.py` as `--prefer-local` / `--prefer-upstream`
globs.
