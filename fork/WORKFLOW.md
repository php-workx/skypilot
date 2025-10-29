# SkyPilot Fork - Development Workflow

**Simple, clean workflow with two main branches and feature branches for PRs**

---

## Branch Structure

```
ojin-release              ← Stable, production-ready (GitHub default)
├── Receives: PRs from ojin-pre-release or feature branches
└── Tagged: After significant releases

ojin-pre-release         ← Active development branch
├── Receives: Direct commits, merges from feature branches
└── Merges to: ojin-release via PR when stable

feature/your-feature     ← Short-lived PR branches
├── Created from: ojin-pre-release or ojin-release
└── Merges to: ojin-pre-release via PR/squash merge
```

---

## Daily Development Workflows

### Workflow 1: Quick Development (No PR)

For small changes, quick iterations:

```bash
# Work directly on ojin-pre-release
git checkout ojin-pre-release
git pull origin ojin-pre-release

# Make changes
vim sky/catalog/new_feature.py
git add .
git commit -m "Add feature X"

# Push
git push origin ojin-pre-release
```

### Workflow 2: Feature Branch Development (With PR)

For larger features that need review:

```bash
# 1. Create feature branch from ojin-pre-release
git checkout ojin-pre-release
git pull origin ojin-pre-release
git checkout -b feature/add-lambda-support

# 2. Develop your feature
vim sky/catalog/lambda_fetcher.py
git add .
git commit -m "Add Lambda catalog fetcher"

# 3. Push feature branch
git push -u origin feature/add-lambda-support

# 4. Create PR on GitHub
# Base: ojin-pre-release
# Compare: feature/add-lambda-support

# 5. After review and merge, clean up
git checkout ojin-pre-release
git pull origin ojin-pre-release
git branch -d feature/add-lambda-support
git push origin --delete feature/add-lambda-support
```

### Workflow 3: Promote to Production

When ojin-pre-release is stable and tested:

```bash
# Option A: Create PR (Recommended)
# Go to GitHub, create PR:
# Base: ojin-release
# Compare: ojin-pre-release
# Review changes, then merge

# Option B: Direct merge
git checkout ojin-release
git pull origin ojin-release
git merge ojin-pre-release
git push origin ojin-release

# Tag the release
git tag v0.10.3-ojin-custom.1
git push origin v0.10.3-ojin-custom.1
```

---

## Upgrading to New SkyPilot Release

When SkyPilot releases a new version (e.g., v0.10.4):

```bash
# Run the upgrade script
./upgrade-to-release.sh

# Script will:
# 1. Rebase ojin-release onto v0.10.4
# 2. Rebase ojin-pre-release onto v0.10.4
# 3. Tag ojin-base-v0.10.4

# Then you:
# 1. Test thoroughly
# 2. Push both branches
git push origin ojin-release --force
git push origin ojin-pre-release --force
git push origin ojin-base-v0.10.4

# 3. Tag the new release
git tag v0.10.4-ojin-custom
git push origin v0.10.4-ojin-custom
```

**The script automatically rebases ALL your custom commits - no cherry-picking needed!**

---

## Visual Workflow Diagram

```
Upstream SkyPilot:
  v0.10.3 ──→ v0.10.4 ──→ v0.11.0

Your Fork:

┌─────────────────────────────────────────────┐
│ ojin-release (stable)                       │
│   v0.10.3                                   │
│     ├── Custom: RunPod fetcher              │
│     └── Custom: Catalog URLs                │
│                                             │
│   (upgrade via script)                      │
│   ↓                                         │
│   v0.10.4                                   │
│     ├── Custom: RunPod fetcher (rebased)    │
│     └── Custom: Catalog URLs (rebased)      │
└─────────────────────────────────────────────┘
                    ↑
                    │ PR when stable
                    │
┌─────────────────────────────────────────────┐
│ ojin-pre-release (development)              │
│   v0.10.3                                   │
│     ├── Custom: RunPod fetcher              │
│     ├── Custom: Catalog URLs                │
│     └── New: Lambda support (in dev)        │
│                                             │
│   (upgrade via script)                      │
│   ↓                                         │
│   v0.10.4                                   │
│     ├── All features rebased                │
│     └── Continue development                │
└─────────────────────────────────────────────┘
                    ↑
                    │ PR or direct commit
                    │
┌─────────────────────────────────────────────┐
│ feature/add-lambda (short-lived)            │
│     └── New: Lambda support                 │
└─────────────────────────────────────────────┘
```

---

## Branch Purposes

| Branch | Purpose | Stability | Push Direct? | PR Target |
|--------|---------|-----------|--------------|-----------|
| **ojin-release** | Production | Stable | No | - |
| **ojin-pre-release** | Development | Testing | Yes | ojin-release |
| **feature/\*** | Feature dev | Unstable | Yes | ojin-pre-release |

---

## Release Versioning

```
v{UPSTREAM_VERSION}-ojin-custom.{INCREMENT}

Examples:
v0.10.3-ojin-custom        ← First release on v0.10.3
v0.10.3-ojin-custom.1      ← More explicit first release
v0.10.3-ojin-custom.2      ← Second release (added features)
v0.10.4-ojin-custom        ← Upgraded to v0.10.4
```

---

## Common Tasks

### Start New Feature
```bash
git checkout ojin-pre-release
git pull
git checkout -b feature/my-feature
```

### Commit to Pre-Release
```bash
git checkout ojin-pre-release
# make changes
git commit -m "Add feature"
git push
```

### Promote to Release
```bash
# Create PR: ojin-release ← ojin-pre-release
# Or:
git checkout ojin-release
git merge ojin-pre-release
git push
git tag v0.10.3-ojin-custom.X
git push --tags
```

### Upgrade Upstream
```bash
./upgrade-to-release.sh
# Follow prompts
# Test
# Push
```

### Hotfix on Release
```bash
git checkout ojin-release
git checkout -b hotfix/critical-bug
# fix bug
git commit -m "Fix critical bug"

# Create PR: ojin-release ← hotfix/critical-bug
# After merge:
git checkout ojin-pre-release
git merge ojin-release  # Pull hotfix into pre-release
```

---

## Advantages of This Workflow

### 1. Clear Separation
- **ojin-release**: Always stable, production-ready
- **ojin-pre-release**: Active development, may be unstable
- **feature/\***: Isolated changes, easy to review

### 2. Flexible Development
- Quick changes: Direct to ojin-pre-release
- Large features: Feature branch → PR
- Both paths work smoothly

### 3. Safe Upgrades
- Script rebases both branches automatically
- Both branches stay in sync
- No manual cherry-picking

### 4. Easy Rollback
```bash
# Rollback release
git checkout ojin-release
git reset --hard v0.10.3-ojin-custom.1

# Rollback pre-release
git checkout ojin-pre-release
git reset --hard origin/ojin-pre-release
```

### 5. Team-Ready
- Multiple developers can work on feature branches
- PR reviews for quality control
- Clear release process

---

## Best Practices

1. **Always branch from ojin-pre-release** for features
2. **Test on ojin-pre-release** before promoting to release
3. **Tag ojin-release** after significant updates
4. **Keep feature branches small** - easier to review
5. **Delete feature branches** after merging
6. **Use the upgrade script** - don't manually rebase

---

## Quick Reference

| Task | Command |
|------|---------|
| New feature branch | `git checkout -b feature/name ojin-pre-release` |
| Quick commit | `git checkout ojin-pre-release && git commit` |
| Promote to release | PR: ojin-release ← ojin-pre-release |
| Upgrade upstream | `./upgrade-to-release.sh` |
| Tag release | `git tag v0.X.Y-ojin-custom.Z` |

---

## Summary

- **Two main branches**: ojin-release (stable), ojin-pre-release (development)
- **Feature branches**: For reviewed development
- **Upgrade script**: Automatically rebases both branches
- **No cherry-picking**: Git handles everything
- **Clean and simple**: Easy to understand and maintain

---

**Ready to develop!** 🚀
