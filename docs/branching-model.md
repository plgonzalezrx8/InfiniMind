# Branching Model

This repository uses a two-long-lived-branch model:

- `master`: production-ready stable branch
- `development`: beta/release-candidate branch

No other long-lived branches should exist.

## Feature and Sprint Branches

All new work must start from `development` using short-lived branches:

- `feature/<name>`
- `sprint/<name>`

Example:

```bash
git checkout development
git pull --ff-only origin development
git checkout -b feature/hook-tuning
```

## Merge Flow

1. implement and test on `feature/*` or `sprint/*`
2. open PR to `development`
3. run beta validation on `development`
4. when release-candidate is approved, merge `development` into `master`
5. tag release from `master`

## Required Gates Before Merge

At minimum:

- `python3 -m pytest services/infinimind-service/tests -q`
- `python3 -m pytest tests/openclaw -q`
- `npm run typecheck && npm run test` in `plugins/infinimind-openclaw-bridge`
- `scripts/secret_scan.sh`

CI branch protection should enforce hosted checks before merging into `development` and `master`.

## Branch Cleanup Policy

After a feature/sprint branch is merged:

1. delete remote feature branch
2. delete local feature branch

Commands:

```bash
git push origin --delete feature/hook-tuning
git branch -d feature/hook-tuning
```

Only `master` and `development` should remain as persistent branches.
