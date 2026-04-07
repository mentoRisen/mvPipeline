---
description: Commit feature branch and output PR link
---

Prepare the branch for a pull request into `main` and return a GitHub URL to open/create the PR manually. Do not merge.

Flow:
1. Confirm current branch with `git branch --show-current`.
2. Stop if current branch is `main` or `master`.
3. Check working tree with `git status --short --branch`.
4. Stage everything: `git add -A`.
5. If there are no staged changes, skip commit and continue.
6. If there are staged changes:
   - Ask once for commit message if none was provided.
   - Commit with the provided message.
7. Push branch (set upstream if needed): `git push -u origin HEAD`.
8. Build PR URL from `origin` and current branch:
   - Read `origin` URL: `git remote get-url origin`
   - Convert SSH/HTTPS remote to web repo URL
   - Output compare URL format:
     - `https://github.com/<owner>/<repo>/compare/main...<branch>?expand=1`
9. Report:
   - current branch
   - commit hash created (or "no new commit")
   - PR URL

Guardrails:
- Do not merge the PR.
- Do not delete local or remote branches.
- Do not force-push.
- If origin is not a GitHub remote, stop and explain that PR URL cannot be generated automatically.
