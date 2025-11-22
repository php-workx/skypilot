# Upgrade Strategy: v0.10.3.post2 → v0.10.5

## Summary

We need to upgrade from `v0.10.3.post2` to `v0.10.5` (488 commits). The main challenge is that we have custom Seeweb implementation that was cherry-picked/merged from an older PR, but Seeweb has since been officially integrated into v0.10.5 with improvements.

## Analysis

### Current Custom Changes (9 commits)
1. `62508f169` - feature: runpod catalog fetcher (#1)
2. `7385d86a3` - feature: custom catalog urls (#2)
3. `d35605fc5` - update release branch (#6)
4. `6871e1818` - fix: restore cudo sdk compatibility with Python 3.10 (#7)
5. `90d513d4c` - feat: add Seeweb provider, improve RunPod availability checking, fix Cudo Python 3.10 compatibility (#8)
6. `a69bd7c94` - fix(runpod): use regional availability (#9)
7. `61f54f489` - fix(serve): auto-fix SSH key permissions on controller startup (#10)
8. `e69d07288` - feat(logs): graceful degradation and controller-only CloudWatch logging (#11)
9. `1a98e2c93` - fix: disable external logging on replicas (#12)

### Upstream Seeweb Changes (in v0.10.5)
- `d9f7c5b0e` - Add Seeweb Provider (#6884) - **Official Seeweb integration**
- `44fa087e8` - Use consistent L40S GPU name for seeweb (#7188)
- `59773bc2e` - Seeweb Docs / Snapshot Update 01 (#7191)
- `e1631a799` - [Docs] Add notes for clouds maintained by third party (#7359)

### Upstream RunPod Changes (in v0.10.5)
- `d56bac264` - Fix runpod check + redact API URL in `sky check` (#7320)
- `0807f15e3` - [Volumes] Fix Runpod Volumes ls (#7386)

## Recommended Strategy: Three-Way Merge with Selective Overwrites

**AVOID** the rebase workflow from `WORKFLOW.md` because it led to too many conflicts. Instead, use a **three-way merge strategy** with selective acceptance of upstream versions.

### Step-by-Step Plan

#### Phase 1: Preparation & Backup
```bash
# 1. Create backup branch
git checkout ojin-release
git branch backup-ojin-release-before-0.10.5-upgrade
git push origin backup-ojin-release-before-0.10.5-upgrade

# 2. Ensure clean working directory
git stash  # if needed

# 3. Document current state
git log v0.10.3.post2..HEAD --oneline > /tmp/custom-commits.txt
git diff v0.10.3.post2..HEAD --stat > /tmp/custom-changes.txt
```

#### Phase 2: Create Upgrade Branch
```bash
# 4. Create upgrade branch from current state
git checkout -b upgrade/v0.10.5-merge
```

#### Phase 3: Merge with Strategy
```bash
# 5. Merge v0.10.5 with strategic options
git merge v0.10.5 --no-commit --no-ff

# This will pause with conflicts - DON'T panic!
```

#### Phase 4: Resolve Conflicts with Categories

##### Category A: ACCEPT UPSTREAM (Complete Overwrite)
These files should use the upstream v0.10.5 version completely:

**Seeweb Files** (upstream is better/newer):
```bash
git checkout --theirs sky/adaptors/seeweb.py
git checkout --theirs sky/catalog/data_fetchers/fetch_seeweb.py
git checkout --theirs sky/catalog/seeweb_catalog.py
git checkout --theirs sky/clouds/seeweb.py
git checkout --theirs sky/provision/seeweb/__init__.py
git checkout --theirs sky/provision/seeweb/config.py
git checkout --theirs sky/provision/seeweb/instance.py
git checkout --theirs sky/templates/seeweb-ray.yml.j2
```

**RunPod Files** (if they have upstream fixes):
```bash
# Check for conflicts first, then selectively accept upstream fixes
git checkout --theirs sky/clouds/runpod.py  # if volume fixes apply
git checkout --theirs sky/provision/runpod/  # if check fixes apply
```

##### Category B: KEEP OURS (Preserve Custom Changes)

**Custom Infrastructure**:
```bash
git checkout --ours .devcontainer/
git checkout --ours .github/workflows/  # our custom CI
git checkout --ours Dockerfile
git checkout --ours Dockerfile_debug
git checkout --ours Makefile
git checkout --ours fork/
git checkout --ours requirements-dev.txt
```

**Custom Features**:
```bash
git checkout --ours sky/catalog/catalog_url_config.py  # custom catalog URLs
```

##### Category C: MANUAL MERGE (Careful Review)

**CloudWatch Logging Changes** - commits #11, #12:
- Files: `sky/serve/`, `sky/skylet/`, `sky/backends/`
- **Strategy**: Review carefully and merge manually
- Keep the graceful degradation and controller-only logging logic
- Integrate with any upstream logging improvements

**SSH Key Permissions Fix** - commit #10:
- File: Likely in `sky/serve/` or `sky/backends/`
- **Strategy**: Check if upstream has similar fix, if not keep ours

**Cudo Python 3.10 Compatibility** - commit #7:
- File: `sky/clouds/cudo.py` or similar
- **Strategy**: Check if upstream fixed this, otherwise keep our fix

**RunPod Availability Checking** - commit #9 (partial):
- Files: `sky/clouds/runpod.py`, `sky/catalog/data_fetchers/fetch_runpod.py`
- **Strategy**:
  - Review our availability filtering logic
  - Integrate with upstream volume/check fixes
  - Preserve the `regions_with_offering()` improvements

**Custom Catalog URL** - commit #2:
- New files should be preserved (Category B)
- Integration points need manual review

##### Category D: DOCUMENTATION & METADATA
```bash
# Accept upstream
git checkout --theirs docs/
git checkout --theirs README.md  # if conflicts

# Keep ours
git checkout --ours CLAUDE.md
git checkout --ours fork/CUSTOMIZATIONS.md
git checkout --ours fork/WORKFLOW.md
```

#### Phase 5: Resolve Specific File Conflicts

For files with conflicts that can't be auto-resolved:

```bash
# List remaining conflicts
git status | grep "both modified"

# For each conflicted file:
# 1. Open in editor
# 2. Review conflict markers (<<<<<<< ======= >>>>>>>)
# 3. Decide strategy per section:
#    - Keep upstream improvements
#    - Preserve our custom logic
#    - Merge both if compatible
```

**Priority Files to Review**:
1. `sky/clouds/runpod.py` - Merge availability logic + upstream fixes
2. `sky/catalog/data_fetchers/fetch_runpod.py` - Preserve availability filtering
3. `sky/serve/` files - Preserve CloudWatch logging logic
4. `sky/backends/` files - Preserve logging changes

#### Phase 6: Testing & Validation

```bash
# After resolving all conflicts
git add .
git commit -m "Merge v0.10.5: Accept upstream Seeweb, preserve custom features

- Accept upstream Seeweb implementation (improved)
- Accept upstream RunPod fixes (volumes, check)
- Preserve custom catalog URL configuration
- Preserve CloudWatch logging enhancements
- Preserve SSH key auto-fix
- Preserve Python 3.10 compatibility fixes
- Preserve RunPod availability filtering

BREAKING: Seeweb implementation completely replaced with upstream version
"

# 7. Run tests
make test

# 8. Review changes
git diff v0.10.5..HEAD --stat
git log v0.10.5..HEAD --oneline

# 9. Test specific functionality
# - Test RunPod with availability filtering
# - Test custom catalog URLs
# - Test Seeweb (with upstream implementation)
# - Test CloudWatch logging
# - Test Cudo with Python 3.10
```

#### Phase 7: Merge to Main Branch

```bash
# If all tests pass
git checkout ojin-release
git merge upgrade/v0.10.5-merge --ff-only  # Should fast-forward

# Or if you prefer a merge commit
git merge upgrade/v0.10.5-merge --no-ff -m "Upgrade to v0.10.5"

# Update tag
git tag -a ojin-base-v0.10.5 -m "Base upstream version v0.10.5"
git push origin ojin-release
git push origin ojin-base-v0.10.5
```

## Conflict Resolution Decision Tree

```
For each conflicted file:
├─ Is it Seeweb-related?
│  └─ YES → Accept upstream (--theirs)
│
├─ Is it custom infrastructure (.github, Dockerfile, Makefile, fork/)?
│  └─ YES → Keep ours (--ours)
│
├─ Is it documentation?
│  ├─ Upstream docs → Accept theirs
│  └─ Our docs (CLAUDE.md, fork/*) → Keep ours
│
└─ Is it core functionality?
   ├─ Does upstream have the same fix? → Accept theirs
   ├─ Is our fix still needed? → Keep ours or merge manually
   └─ Can both coexist? → Merge both manually
```

## Key Principles

1. **Trust Upstream for Seeweb**: The official Seeweb implementation is better maintained
2. **Preserve Critical Customizations**: CloudWatch logging, catalog URLs, availability filtering
3. **Integrate, Don't Override**: Where possible, merge our logic with upstream improvements
4. **Test Thoroughly**: Each custom feature must be validated after merge
5. **Document Changes**: Update `fork/CUSTOMIZATIONS.md` with any changes

## Files Requiring Special Attention

### High Risk (Manual Review Required)
- `sky/clouds/runpod.py` - Availability logic + upstream fixes
- `sky/catalog/data_fetchers/fetch_runpod.py` - Catalog filtering
- `sky/serve/serve.py` or similar - CloudWatch logging
- `sky/backends/backend_utils.py` or similar - Logging configuration

### Medium Risk (Review Recommended)
- `sky/clouds/cudo.py` - Python 3.10 compatibility
- `sky/authentication.py` - SSH key permissions (if modified)
- Any files in `sky/skylet/` - CloudWatch integration

### Low Risk (Can Auto-Resolve)
- Test files
- GitHub workflows
- Documentation
- DevContainer config

## Rollback Plan

If the upgrade fails or introduces critical bugs:

```bash
# Rollback to backup
git checkout ojin-release
git reset --hard backup-ojin-release-before-0.10.5-upgrade
git push origin ojin-release --force-with-lease

# Delete failed upgrade branch
git branch -D upgrade/v0.10.5-merge
```

## Post-Upgrade Tasks

1. Update `fork/CUSTOMIZATIONS.md` with changes
2. Update `CLAUDE.md` if development process changed
3. Test all custom features:
   - RunPod availability filtering
   - Custom catalog URLs (env vars)
   - Seeweb provisioning (with new upstream code)
   - CloudWatch logging (controller-only)
   - Cudo on Python 3.10
4. Update container image tags in deployment
5. Notify team of Seeweb implementation change

## Expected Outcome

- ✅ Base version: v0.10.5 (488 new commits)
- ✅ Seeweb: Upstream implementation (better maintained)
- ✅ RunPod: Our availability filtering + upstream volume/check fixes
- ✅ Custom catalog URLs: Preserved
- ✅ CloudWatch logging: Preserved (controller-only)
- ✅ SSH key auto-fix: Preserved (if still needed)
- ✅ Python 3.10 compatibility: Preserved (if still needed)
- ✅ All tests passing
- ✅ Clean git history with clear merge commit

## Advantages Over Rebase

1. **Preserves history**: Clear record of what was custom vs. upstream
2. **Easier conflict resolution**: Can accept entire files with `--theirs/--ours`
3. **Safer**: Can test before finalizing, easier to rollback
4. **Team-friendly**: Other developers can review the merge commit
5. **Less conflict-prone**: Rebase replays each commit, merge resolves once

## Timeline Estimate

- Phase 1-2: 10 minutes
- Phase 3: 2 minutes (merge command)
- Phase 4: 30-60 minutes (strategic conflict resolution)
- Phase 5: 1-2 hours (manual merge of complex files)
- Phase 6: 2-4 hours (testing)
- Phase 7: 15 minutes (merge to main)

**Total**: 4-8 hours (depending on conflicts)