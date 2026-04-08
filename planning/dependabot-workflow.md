# Dependabot Workflow

Dependabot opens PRs automatically every Monday for outdated or vulnerable dependencies across `frontend/` (npm), `backend/` (pip), and `.github/workflows/` (GitHub Actions). This doc describes how to handle them.

---

## The goal: keep the queue at zero

A long backlog of open Dependabot PRs means security updates are being deferred. The target is to process every PR within a day or two of it opening.

---

## PRs that pass CI → merge immediately

If CI is green, merge it. That's the entire purpose of having branch protection + a test suite. There is no reason to hold a passing dependency update — waiting introduces drift and makes future updates harder.

Dependabot PRs can be merged one at a time or batched if they are for independent packages. If two PRs touch the same package (e.g. a transitive dep updated by multiple direct dep upgrades), merge them sequentially and let Dependabot auto-close the superseded ones.

---

## PRs that fail CI → investigate, don't close

A failing Dependabot PR means one of two things:

**1. The update introduced a breaking change**

The dependency changed its API, removed a function, or altered behaviour that your code relies on. This is the Dependabot PR doing its job — it surfaced an incompatibility before it hit production.

What to do:
- Read the CI failure to identify what broke
- Check the package's changelog or release notes for migration guidance
- Fix your code in a separate PR, merge that first, then re-run CI on the Dependabot PR and merge it
- If the fix is complex and the vulnerability is low severity, it is acceptable to leave the PR open temporarily — but set a concrete deadline to address it

**2. CI failure unrelated to the dependency**

A flaky test, a network timeout hitting an external service, or a pre-existing broken test that happens to surface on this branch.

What to do:
- Re-run the failing job
- If it passes on retry, merge
- If it keeps failing on retry, investigate whether the test was already broken on `main`

---

## Never close a Dependabot PR without merging it

Closing a PR without merging does not resolve the underlying alert. Dependabot will reopen it at the next scheduled run (weekly Monday) because the vulnerability or outdated version still exists. The only ways to permanently resolve a Dependabot alert are:

- **Merge the PR** — the fix lands in `main`
- **Dismiss the alert** in the Security tab (GitHub → Security → Dependabot alerts) with a documented reason — use this only for confirmed false positives or cases where the vulnerable code path is genuinely unreachable

Do not use "close PR" as a way to make the queue look smaller. It just moves the noise to next week.

---

## When a PR cannot be merged and cannot be fixed quickly

If a major version bump requires significant migration work that cannot be done immediately:

1. Leave the PR open (do not close it)
2. Add a comment on the PR explaining the blocker and estimated timeline
3. If the package has a known vulnerability, check its severity — a critical CVE in a production dependency warrants prioritising the migration work

---

## Future: SARIF-based CVE monitoring (when repo goes public)

Once the GitHub repo is public, a Trivy SARIF upload step will be added to CI. This surfaces OS-layer and container CVEs (including `will_not_fix` findings) in the GitHub Security tab, separate from the deploy gate. This closes the gap where unfixed CVEs are silenced by `--ignore-unfixed` on deploys but still need to be tracked for when a fix eventually ships.

See `planning/11-adjusted-sprint-plan.md` → "Continuous CVE monitoring" for implementation details.
