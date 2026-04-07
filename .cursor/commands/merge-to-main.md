---
description: Merge current branch into main safely
---

Merge the current feature branch into `main` safely.

Checklist:
1. Confirm git working tree is clean, or summarize uncommitted changes.
2. Identify the current branch.
3. Run relevant tests, lint, and typecheck for this repo.
4. Summarize what is about to be merged.
5. Switch to `main`.
6. Pull latest `main`.
7. Merge the current branch into `main`.
8. If there are conflicts, stop and explain them clearly.
9. After merge, run a quick verification step if appropriate.
10. Push `main`.
11. Report exactly what was done, including branch names and merge result.

Do not force-push.
Do not delete branches unless explicitly asked.
Stop before destructive actions if the repo state looks risky.