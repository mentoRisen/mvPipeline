---
description: Create PR, merge to main, switch back
---

Create a pull request from the current feature branch into `main`, merge it, and return the workspace to `main`.

Fast flow (experimental repo):
1. Confirm git working tree is clean, or summarize uncommitted changes.
2. Identify current branch. If already on `main`, stop.
3. Push current branch if needed: `git push -u origin HEAD`.
4. Create PR to `main`:
   - `gh pr create --base main --fill`
   - If title/body are unclear, ask once, then continue.
5. Merge PR (prefer squash) and keep branch:
   - `gh pr merge --squash`
6. Switch local workspace to `main`: `git checkout main`.
7. Pull latest `main`: `git pull --ff-only`.
8. Report final state:
   - merged PR number/url
   - merge method used
   - current branch and `git status -sb`

Guardrails:
- Do not force-push.
- If merge conflicts or blocked checks appear, stop and explain the blocker.
- Do not delete local or remote branches unless explicitly asked.
