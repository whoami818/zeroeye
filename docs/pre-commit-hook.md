# Pre-commit Hook

Zeroeye uses a pre-commit hook to ensure diagnostic build artifacts are
generated and staged before every commit.

## What it does

1. **Change detection** — hashes all `.py` files; skips rebuild if nothing changed
2. **Build** — runs `python3 build.py` with a live countdown timer
3. **Stage** — `git add`s the latest `diagnostic/build-XXX.logd` and `.json`
4. **Fail-safe** — aborts commit if `build.py` exits non-zero

## Installation

```bash
make install-hooks
```

This symlinks `tools/pre-commit` → `.git/hooks/pre-commit`.

## Manual run

```bash
./tools/pre-commit
```

## Skipping the hook

In emergencies, use `git commit --no-verify`. Don't make a habit of it.
