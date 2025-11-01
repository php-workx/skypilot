# SkyPilot Fork – Development Workflow

**Single release branch with short-lived feature branches**

---

## Branch Structure

```
ojin-release            ← Default branch; always releasable
├── Receives: PRs from feature/* or hotfix/* branches
└── Tagged: Automatically per merge (container + git tags)

feature/your-feature    ← Short-lived development branches
├── Created from: ojin-release
└── Merges to: ojin-release via PR/squash merge
```

---

## Daily Development Flow

Keep `ojin-release` clean by merging through PRs—even for fast fixes—so code review, CI, and the automated release tagging stay consistent.

```bash
git checkout ojin-release
git pull origin ojin-release
git checkout -b feature/add-lambda-support

# develop...
git commit -am "Add Lambda catalog fetcher"
git push -u origin feature/add-lambda-support
```

Open a PR to `ojin-release`. After merging, delete the feature branch locally and remotely.

### Hotfixing Production

```bash
# Branch directly from ojin-release
git checkout ojin-release
git pull
git checkout -b hotfix/critical-bug

# fix...
git commit -am "Fix critical bug"
git push -u origin hotfix/critical-bug
# PR back into ojin-release
```

Because `ojin-release` is the deployment branch, the merged hotfix becomes the next container/git tag automatically.

---

## Release Process

`ojin-release` is the only long-lived branch. Every merge triggers CI, builds the Docker image, and produces a tag with the format:

```
{SKYPILOT_BASE_VERSION}-ojin.{YYYYMMDD}.{N}
```

where:

- `SKYPILOT_BASE_VERSION` is defined in `.github/workflows/publish-to-ecr.yml`
- `YYYYMMDD` is the UTC date of the build
- `N` increments per day

Both the container image and the Git repo receive the same tag—no `latest` tag is published.

---

## Upgrading to a New SkyPilot Release

Use the upgrade script to rebase your fork onto the latest upstream version:

```bash
./upgrade-to-release.sh
```

The script:

1. Rebases `ojin-release` onto the chosen upstream tag
2. Creates/updates the `ojin-base-{upstream-tag}` marker tag

After it finishes:

```bash
# Run tests, validate everything
git push origin ojin-release --force-with-lease  # only if rebase changes history
git push origin ojin-base-v0.10.4
```

Then merge new work as usual; the GitHub Actions workflow continues tagging images off `ojin-release`.

---

## Visual Reference

```
Upstream SkyPilot:
  v0.10.3 ──→ v0.10.4 ──→ v0.11.0

Your fork:

┌────────────────────────────────────────┐
│ ojin-release (default)                 │
│   v0.10.3 + custom patches             │
│     ├── Merge feature/add-lambda       │
│     └── Merge hotfix/fix-xyz           │
│                                        │
│ (upgrade via script)                   │
│   ↓                                    │
│  v0.10.4 + rebased patches             │
└────────────────────────────────────────┘
        ↑
        │ PRs from feature/hotfix branches
        │
┌────────────────────────────────────────┐
│ feature/add-lambda (short-lived)       │
└────────────────────────────────────────┘
```

---

## Quick Reference

| Task                  | Command |
|-----------------------|---------|
| Sync local repo       | `git checkout ojin-release && git pull` |
| New feature branch    | `git checkout -b feature/name ojin-release` |
| Merge via PR          | Base `ojin-release`, compare `feature/name` |
| Upgrade upstream      | `./upgrade-to-release.sh` |
| Tagging               | Handled automatically by CI |

---

## Best Practices

1. Keep `ojin-release` green—run tests and review before merging.
2. Delete feature branches after merging to avoid clutter.
3. When upgrading upstream, close all open PRs or rebase them afterwards.
4. Bump `SKYPILOT_BASE_VERSION` in the workflow when adopting a new upstream release so tags stay accurate.
5. Because no `latest` tag exists, always reference an explicit version in deployments.

---

Happy coding! 🚀
