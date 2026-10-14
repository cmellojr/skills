---
type: template
resource: merge-plan-template
---

# Merge plan template

Write the plan to `docs/` or `.memory/plan/` in the target repository (follow
whatever location past plans used). Present it to the user and wait for
approval before Stage 4.

```markdown
# Merge Plan: upstream/<branch> -> <fork>

## Goal

Integrate upstream's N commit(s) (<range or first..last>) into the fork,
resolving all M predicted conflicts while preserving fork-specific changes.

## Discovered policies

- Prefer local: <paths> (source: <file>)
- Prefer upstream: <paths> (source: <file>)
- Commit style: <rule> (source: <file>)
- Validations: <commands> (source: <file>)

## Current state (before)

Fork-specific additions not present upstream:

- <file or area> — <why it exists>

Upstream changes being pulled in:

- <file or area> — <what changed>

## Affected areas

- <directory> — <scope>
- <directory> — <scope>

## Implementation phases

### Phase 0: Preparation

- Create branch: `git checkout -b sync/upstream-<branch>-<YYYYMMDD>`
- Acceptance criteria: branch created from <target>, clean tree.

### Phase 1..N: Conflicts by category

**Files:** <list>

**Resolution strategy:**
- <file>: accept upstream for <aspect>; preserve fork's <aspect>
- <file>: keep local entirely (matched prefer-local policy <pattern>)

**Acceptance criteria:** <verifiable outcome per file>
**Dependencies:** Phase <n-1>.

### Phase N+1: Final verification

- Zero residual conflict markers: `git diff --check`
- Validations pass: <commands from discovered policies>
- Clean tree and merge commit created (Google-style message per repo rules)
```

## Writing rules

- One phase per coherent file group, ordered by dependency.
- Every resolution must be either a policy application ("matched
  prefer-local `rules/**`") or an explicit decision stated in the plan.
- Acceptance criteria must be commands or observable facts, not adjectives.
