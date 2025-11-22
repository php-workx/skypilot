# SkyPilot Fork Upgrade Process

**Last Updated:** 2025-11-22
**Last Upgrade:** v0.10.3.post2 → v0.10.5 (488 commits)

## Overview

This document describes the proven process for upgrading our SkyPilot fork to new upstream versions. The process uses a **three-way merge strategy** which is much easier than rebasing when dealing with hundreds of upstream commits.

## Why Merge Instead of Rebase?

**Rebase Problems:**
- Replays each custom commit on top of upstream (9 commits × 488 upstream = many conflicts)
- Each conflict needs to be resolved multiple times
- Easy to lose custom changes
- Hard to rollback if something goes wrong

**Merge Advantages:**
- ✅ Resolve conflicts once
- ✅ Can accept entire files with `--theirs` or `--ours`
- ✅ Clear history of what was merged
- ✅ Easy to test before finalizing
- ✅ Safer rollback process

## Prerequisites

1. **Clean working directory:**
   ```bash
   git status  # Should be clean
   ```

2. **Updated upstream remote:**
   ```bash
   git remote add upstream https://github.com/skypilot-org/skypilot.git 2>/dev/null || true
   git fetch upstream --tags
   ```

3. **Review custom changes:**
   ```bash
   # See what we've changed since last base version
   git log <LAST_BASE_VERSION>..HEAD --oneline
   git diff <LAST_BASE_VERSION>..HEAD --stat
   ```

4. **Check fork/CUSTOM_CHANGES.md:**
   - Review what features we've added
   - Identify files we've intentionally modified
   - Note any integration points with upstream

## Step-by-Step Upgrade Process

### Phase 1: Preparation (10 minutes)

```bash
# 1. Create backup branch
git checkout ojin-release
git branch backup-ojin-release-before-<VERSION>-upgrade
git push origin backup-ojin-release-before-<VERSION>-upgrade

# 2. Document current state
git log <LAST_VERSION>..HEAD --oneline > /tmp/custom-commits.txt
git diff <LAST_VERSION>..HEAD --stat > /tmp/custom-changes.txt

# 3. Create upgrade branch
git checkout -b upgrade/<VERSION>-merge
```

### Phase 2: Merge (2 minutes)

```bash
# 4. Initiate merge (will pause with conflicts)
git merge <VERSION> --no-commit --no-ff
```

### Phase 3: Resolve Conflicts (1-3 hours)

Use the decision tree in the next section. Generally:

```bash
# Category A: Accept upstream completely
git checkout --theirs <file>
git add <file>

# Category B: Keep our version completely
git checkout --ours <file>
git add <file>

# Category C: Manual merge (edit the file)
# Resolve conflict markers manually
git add <file>
```

**Common Patterns:**

1. **New cloud providers (Shadeform, PrimeIntellect, etc.):**
   ```bash
   # Just add the new imports/registrations
   git checkout --theirs sky/clouds/__init__.py
   # Then manually add back any custom clouds if needed
   ```

2. **Seeweb or other cherry-picked features:**
   ```bash
   # Accept upstream - they have the official version
   git checkout --theirs sky/adaptors/seeweb.py
   git checkout --theirs sky/clouds/seeweb.py
   git checkout --theirs sky/provision/seeweb/
   ```

3. **Our custom features (catalog URLs, logging, etc.):**
   ```bash
   # Keep our changes
   git checkout --ours sky/catalog/catalog_url_config.py
   # Or manually merge if upstream modified same area
   ```

### Phase 4: Test (2-4 hours)

```bash
# 5. Install dependencies
make install

# 6. Run tests
make test 2>&1 | tee test_upgrade_output.log

# 7. Review test results
# Compare failures to pre-upgrade baseline
# New failures = regression from merge
# Same failures = pre-existing issues

# 8. Verify custom features
# - Test RunPod availability filtering
# - Test custom catalog URLs
# - Test CloudWatch logging
# - Test any cloud-specific customizations
```

### Phase 5: Commit & Deploy (15 minutes)

```bash
# 9. Commit the merge
git commit -m "Merge <VERSION>: integrate upstream changes

- Accept upstream Seeweb implementation
- Preserve custom catalog URL configuration
- Preserve CloudWatch logging enhancements
- Preserve Python 3.10 compatibility fixes
- Add upstream clouds: <NEW_CLOUDS>

Conflicts resolved: <NUMBER>
Tests: <PASSED/FAILED> (baseline: <BASELINE>)
"

# 10. Merge to main branch
git checkout ojin-release
git merge upgrade/<VERSION>-merge --ff-only

# 11. Tag the base version
git tag -a ojin-base-<VERSION> -m "Base upstream version <VERSION>"

# 12. Push to remote
git push origin ojin-release
git push origin ojin-base-<VERSION>
git push origin upgrade/<VERSION>-merge  # Keep for reference
```

### Phase 6: Update Documentation (15 minutes)

```bash
# Update fork/CUSTOM_CHANGES.md with any new changes
# Update this file with lessons learned
# Update fork/CUSTOMIZATIONS.md if features changed
```

## Conflict Resolution Decision Tree

```
For each conflicted file:

1. Is it a feature we cherry-picked that's now in upstream?
   ├─ YES → Accept upstream (--theirs)
   └─ NO → Continue...

2. Is it a new cloud provider or integration we don't have?
   ├─ YES → Accept upstream (--theirs)
   └─ NO → Continue...

3. Is it custom infrastructure (.github, Dockerfile, Makefile, fork/)?
   ├─ YES → Keep ours (--ours)
   └─ NO → Continue...

4. Is it documentation?
   ├─ Upstream docs → Accept theirs
   ├─ Our docs (CLAUDE.md, fork/*) → Keep ours
   └─ NO → Continue...

5. Is it a custom feature we need to preserve?
   ├─ Does upstream have same fix? → Accept theirs
   ├─ Is our fix still needed? → Keep ours or merge manually
   └─ Can both coexist? → Merge both manually

6. Is it a test file?
   ├─ Tests for our custom features → Keep ours
   ├─ General test updates → Accept theirs
   └─ Conflicts in shared tests → Merge manually
```

## Files That Typically Need Manual Attention

### High Priority (Our Custom Features)

**Custom Catalog URLs:**
- `sky/catalog/catalog_url_config.py` - Always keep ours

**CloudWatch Logging:**
- `sky/logs/aws.py` - Usually auto-merges, verify controller-only logic

**RunPod Availability:**
- `sky/clouds/runpod.py` - Merge our availability logic with upstream fixes
- `sky/catalog/data_fetchers/fetch_runpod.py` - Keep availability filtering

**Cudo Python 3.10:**
- `sky/clouds/cudo.py` - Keep our compatibility fixes unless upstream fixed

### Medium Priority (Integration Points)

**Cloud Registration:**
- `sky/__init__.py` - Add new upstream clouds, keep Seeweb
- `sky/clouds/__init__.py` - Add new cloud imports
- `sky/provision/__init__.py` - Add new provision modules
- `sky/backends/backend_utils.py` - Add new authentication handlers

**Dependencies:**
- `sky/setup_files/dependencies.py` - Accept upstream (they track all dependencies)
- `requirements-dev.txt` - Accept upstream

### Low Priority (Usually Auto-Merge)

- Test files (unless testing custom features)
- Documentation (upstream docs)
- GitHub workflows (we disabled upstream CI)

## Automated Helper Script

We can automate the repetitive parts. See `fork/upgrade-helper.sh`:

```bash
#!/bin/bash
# Usage: ./fork/upgrade-helper.sh v0.10.6

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version-tag>"
    exit 1
fi

set -e

echo "=== SkyPilot Fork Upgrade Helper ==="
echo "Target version: $VERSION"
echo ""

# Phase 1: Preparation
echo "📋 Phase 1: Preparation"
git checkout ojin-release
git branch backup-ojin-release-before-$VERSION-upgrade
git push origin backup-ojin-release-before-$VERSION-upgrade

# Document current state
LAST_TAG=$(git describe --tags --abbrev=0 ojin-release)
git log $LAST_TAG..HEAD --oneline > /tmp/custom-commits-$VERSION.txt
git diff $LAST_TAG..HEAD --stat > /tmp/custom-changes-$VERSION.txt

echo "✅ Backup created: backup-ojin-release-before-$VERSION-upgrade"
echo "✅ Custom commits saved to: /tmp/custom-commits-$VERSION.txt"
echo "✅ Custom changes saved to: /tmp/custom-changes-$VERSION.txt"
echo ""

# Phase 2: Merge
echo "📦 Phase 2: Creating upgrade branch"
git checkout -b upgrade/$VERSION-merge

echo "🔀 Starting merge with $VERSION"
echo "⚠️  MANUAL ACTION REQUIRED NEXT ⚠️"
echo ""
echo "Run the following command:"
echo "  git merge $VERSION --no-commit --no-ff"
echo ""
echo "Then use the conflict resolution strategy from UPGRADE_PROCESS.md"
echo ""
echo "After resolving conflicts:"
echo "  make install          # Update dependencies"
echo "  make test             # Run tests"
echo "  git commit            # Commit the merge"
echo ""
```

## Testing Checklist

After merge, verify:

- [ ] `make install` completes without errors
- [ ] `make test` runs (compare failures to baseline)
- [ ] `sky check` shows all expected clouds
- [ ] Custom catalog URLs work (if configured)
- [ ] RunPod availability filtering works
- [ ] CloudWatch logging works (controller-only)
- [ ] Seeweb provisioning works (upstream implementation)
- [ ] Version in `sky/__init__.py` updated
- [ ] No import errors in Python

## Rollback Procedure

If the upgrade fails or introduces critical bugs:

```bash
# Option 1: Rollback ojin-release
git checkout ojin-release
git reset --hard backup-ojin-release-before-<VERSION>-upgrade
git push origin ojin-release --force-with-lease

# Option 2: Keep upgrade branch for later
git checkout ojin-release  # Leave upgrade branch for debugging
git branch -D upgrade/<VERSION>-merge  # Delete after fixing

# Clean up
git branch -d upgrade/<VERSION>-merge
```

## Post-Upgrade Tasks

1. **Update Documentation:**
   - [ ] Update `fork/CUSTOM_CHANGES.md` with date and version
   - [ ] Update `fork/CUSTOMIZATIONS.md` if features changed
   - [ ] Update this file with lessons learned

2. **Notify Team:**
   - [ ] Announce upgrade in team channel
   - [ ] Note any breaking changes
   - [ ] Update deployment instructions if needed

3. **Update CI/CD:**
   - [ ] Verify container builds work
   - [ ] Update deployment tags
   - [ ] Test in staging environment

## Common Issues & Solutions

### Issue: Missing Dependencies

**Symptom:** `ModuleNotFoundError` when running tests

**Solution:**
```bash
make install  # Ensures all dependencies updated
# Or manually:
pip install <missing-package>
```

### Issue: Test Failures

**Symptom:** More test failures than baseline

**Solution:**
1. Check if failures are in custom code
2. Review merged files for our custom logic
3. Check `sky/logs/aws.py` for CloudWatch logic
4. Verify `sky/clouds/runpod.py` for availability filtering

### Issue: Import Cycles

**Symptom:** Circular import errors

**Solution:**
- Upstream refactored module structure
- Check if they moved functions to new modules
- Update our imports to match new structure

### Issue: API Changes

**Symptom:** Function signature mismatches

**Solution:**
- Check upstream changelog for API changes
- Update our code to use new API
- Check if they added new required parameters

## Lessons Learned

### From v0.10.3.post2 → v0.10.5 Upgrade

**What Worked Well:**
1. ✅ Three-way merge strategy - much easier than rebase
2. ✅ Accepting upstream Seeweb completely - less maintenance
3. ✅ Auto-merge handled RunPod and CloudWatch changes perfectly
4. ✅ Clear categorization of conflicts (A/B/C) helped decision making
5. ✅ Backup branch made the process safer
6. ✅ Testing before commit caught dependency issues

**What Could Be Improved:**
1. ⚠️ Need better tracking of custom changes (see CUSTOM_CHANGES.md)
2. ⚠️ Should run `make install` before testing (we forgot initially)
3. ⚠️ Need to document which test failures are expected baseline

**Statistics:**
- **Time:** ~5 hours total (including testing)
- **Conflicts:** 24 files with conflicts
- **Resolution:** 4 auto-merged, 20 manually resolved
- **Tests:** 1 failure (same as pre-upgrade baseline)
- **Success Rate:** 100% (no regressions)

## Future Improvements

1. **Automated Conflict Detection:**
   - Script to identify likely conflict categories before merge
   - Pre-analyze which files we've modified vs. upstream changes

2. **Better Change Tracking:**
   - Implement CUSTOM_CHANGES.md to track all intentional modifications
   - Tag commits with custom feature markers

3. **Test Baseline Tracking:**
   - Document expected test failures per version
   - Auto-compare test results to baseline

4. **Merge Simulation:**
   - Dry-run merge to estimate conflict count before starting
   - Generate conflict report for planning

## Quick Reference Commands

```bash
# Start upgrade
./fork/upgrade-helper.sh v0.10.x

# Check conflicts
git status --short | grep "^[UA][UA]"

# Accept upstream
git checkout --theirs <file> && git add <file>

# Keep ours
git checkout --ours <file> && git add <file>

# Test
make install && make test

# Commit
git commit -m "Merge v0.10.x: integrate upstream changes"

# Tag
git tag -a ojin-base-v0.10.x -m "Base upstream version v0.10.x"
```

## Contact & Support

For questions about the upgrade process:
1. Review this document
2. Check `fork/CUSTOM_CHANGES.md` for our modifications
3. Review the previous upgrade PR for examples
4. Check git history: `git log --grep="Merge v0.10"`

---

**Remember:** The merge strategy is safer than rebase. Don't rush. Test thoroughly.
