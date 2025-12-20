# Upgrade Strategy: v0.10.5 → v0.11.1

## Summary

We need to upgrade from `v0.10.5` to `v0.11.1` (208 commits). Since the last upgrade, we've added 9 custom commits (#13-22) with significant controller and Kubernetes improvements. The main challenges are:

1. **Controller-related changes**: Both we and upstream modified controller logic
2. **RunPod catalog refactor**: Major upstream changes to `fetch_runpod.py` (698 lines)
3. **Kubernetes improvements**: Both we and upstream made K8s fixes
4. **Dependency management**: We added dependency fixes that may conflict

## Current State Analysis

### Our Custom Changes Since v0.10.5 (9 commits)

1. `d1f99378b` - Update SKYPILOT_BASE_VERSION to 0.10.5 (#13) - *metadata*
2. `109844688` - fix(serve): clean up orphaned replica records during service shutdown (#15)
3. `a2c091a26` - fix(serve controller): surface dependency installation errors (#14)
4. `b01331e51` - feat(serve): set controller container (#17)
5. `6206a8690` - feat: add SKYPILOT_CONTROLLER_IMAGE support and fix controller Python interpreter (#18)
6. `8e2826bfb` - fix: use $HOME instead of hardcoded /home/sky for controller Python path (#19)
7. `700267714` - fix: missing python packages (#20)
8. `0c26e5883` - fix(k8s): ignore evicted pods (#21)
9. `b91b33366` - fix(deps): incompatibility between aiodns and pycares (#22)

**Key Custom Features:**
- Controller image override (`SKYPILOT_CONTROLLER_IMAGE`)
- Controller dependency installation improvements
- Kubernetes evicted pods handling
- Serve orphaned replica cleanup
- Plus existing features from v0.10.5 upgrade

### Upstream v0.11.1 Highlights

**Major Changes:**
- `a7380a514` - Release 0.11.1 (#8310)
- `b2f351972` - Release 0.11.0 (#8255)
- `6c979cea0` - Fixed stall txn block write operation (#8285)
- `38480ede7` - [Consolidation] Fix env vars and skip the status refresh for controllers (#8106)
- `5a380e9d3` - [Pool][Serve] Resource management coordination for jobs/pool; Move to SDK + Threading for SkyServe provision/terminate (#7332)
- `dad0e910c` - [GCP] Fix B200 spot instance support in catalog fetcher (#8125)
- `206da1cf5` - Install tomli explicitly during Runpod setup (#8018)

**Files with Major Changes:**
- `sky/catalog/data_fetchers/fetch_runpod.py` - **698 new lines** (major refactor)
- `sky/clouds/aws.py` - 354 line changes
- `sky/clouds/kubernetes.py` - 96 line changes
- `sky/jobs/server/core.py` - 36 line changes (we also modified this!)
- `sky/provision/kubernetes/instance.py` - changes (we also modified this!)
- `sky/utils/controller_utils.py` - likely changes (we modified this!)

## Risk Assessment

### 🔴 HIGH RISK - Requires Careful Manual Merge

**1. Controller Logic Conflicts**
- **Files:** `sky/jobs/server/core.py`, `sky/serve/server/impl.py`
- **Why:** We added `inject_controller_image_config()` calls; upstream likely changed controller initialization
- **Strategy:** Merge both - our image injection + upstream improvements

**2. RunPod Catalog Fetcher**
- **File:** `sky/catalog/data_fetchers/fetch_runpod.py`
- **Why:** 698 new lines upstream; we have availability filtering
- **Strategy:** Carefully merge our availability logic into their refactor

**3. Kubernetes Instance Provisioning**
- **File:** `sky/provision/kubernetes/instance.py`
- **Why:** We added evicted pod filtering; upstream likely has improvements
- **Strategy:** Merge our evicted pod logic with upstream changes

**4. Controller Utils**
- **File:** `sky/utils/controller_utils.py`
- **Why:** We added dependency installation fixes; upstream may have similar fixes
- **Strategy:** Check if upstream fixed the same issues; merge carefully

### 🟡 MEDIUM RISK - Likely Auto-Merge with Verification

**5. Common Utils**
- **File:** `sky/utils/common_utils.py`
- **Why:** We added new function `inject_controller_image_config()`
- **Strategy:** Should auto-merge (we added, they modified elsewhere)

**6. Controller Templates**
- **Files:** `sky/templates/jobs-controller.yaml.j2`, `sky/templates/sky-serve-controller.yaml.j2`
- **Why:** We changed `$HOME` paths and quoting; upstream may have template changes
- **Strategy:** Merge our fixes with their improvements

**7. Dependencies**
- **File:** `sky/setup_files/dependencies.py`
- **Why:** We added version pins for aiodns/pycares
- **Strategy:** Generally accept upstream; verify our pins are compatible

### 🟢 LOW RISK - Preserve Existing Custom Features

**8. Existing Custom Features (from v0.10.5)**
- Custom catalog URLs - no changes expected
- CloudWatch logging - likely safe
- Cudo Python 3.10 - check if upstream fixed
- RunPod availability - needs merge with refactor
- Orphaned replica cleanup - likely safe

## Recommended Strategy: Three-Way Merge

Use the proven three-way merge strategy from the v0.10.5 upgrade.

### Step-by-Step Plan

#### Phase 1: Preparation & Backup (10 minutes)

```bash
# 1. Ensure we're on ojin-release with clean state
git checkout ojin-release
git status  # Should be clean

# 2. Create backup branch
git branch backup-ojin-release-before-v0.11.1-upgrade
git push origin backup-ojin-release-before-v0.11.1-upgrade

# 3. Document current state
BASE_TAG="v0.10.5"
git log $BASE_TAG..HEAD --oneline > /tmp/custom-commits-v0.11.1.txt
git diff $BASE_TAG..HEAD --stat > /tmp/custom-changes-v0.11.1.txt
git diff $BASE_TAG..HEAD --name-only | sort > /tmp/custom-files-v0.11.1.txt

# 4. Document upstream changes
git log v0.10.5..v0.11.1 --oneline > /tmp/upstream-commits-v0.11.1.txt
git diff v0.10.5..v0.11.1 --stat > /tmp/upstream-changes-v0.11.1.txt

# 5. Create upgrade branch
git checkout -b upgrade/v0.11.1-merge
```

#### Phase 2: Initiate Merge (2 minutes)

```bash
# 6. Start the merge (will pause with conflicts)
git merge v0.11.1 --no-commit --no-ff

# This will show conflicts - don't panic!
git status --short | grep "^[UA][UA]" > /tmp/conflicts-v0.11.1.txt
```

#### Phase 3: Resolve Conflicts by Category (2-4 hours)

##### Category A: ACCEPT UPSTREAM (Complete Overwrite)

**Infrastructure & CI/CD** (we keep our versions):
```bash
git checkout --ours .github/workflows/
git checkout --ours .devcontainer/
git checkout --ours Dockerfile
git checkout --ours Dockerfile_debug
git checkout --ours Makefile
git checkout --ours fork/
git add .github/ .devcontainer/ Dockerfile* Makefile fork/
```

**Upstream Documentation**:
```bash
# Accept upstream docs (if conflicts)
git checkout --theirs docs/
git checkout --theirs README.md  # unless we customized it
git add docs/ README.md
```

**Dependencies** (generally accept upstream):
```bash
# Check our custom pins first!
git diff HEAD sky/setup_files/dependencies.py

# If upstream includes our aiodns/pycares fixes:
git checkout --theirs sky/setup_files/dependencies.py
git add sky/setup_files/dependencies.py

# Otherwise, manually merge our pins
```

##### Category B: KEEP OURS (Custom Infrastructure)

**Our Documentation**:
```bash
git checkout --ours CLAUDE.md
git checkout --ours fork/CUSTOM_CHANGES.md
git checkout --ours fork/UPGRADE_PROCESS.md
git checkout --ours fork/UPGRADE_STRATEGY_v0.10.5.md
git add CLAUDE.md fork/
```

**Custom Catalog URLs** (unchanged feature):
```bash
# If there's a conflict (unlikely)
git checkout --ours sky/catalog/catalog_url_config.py
git add sky/catalog/catalog_url_config.py
```

##### Category C: MANUAL MERGE (Careful Integration)

**CRITICAL: These require manual resolution - DO NOT auto-accept either side!**

**1. RunPod Catalog Fetcher** 🔴 HIGH PRIORITY
```bash
# Check the conflict
git diff sky/catalog/data_fetchers/fetch_runpod.py

# Strategy:
# - Upstream has major refactor (698 lines)
# - We have availability filtering
# - Need to port our filtering logic to their new structure

# Steps:
# 1. Accept their version as base
git checkout --theirs sky/catalog/data_fetchers/fetch_runpod.py

# 2. Review our changes
git show HEAD:sky/catalog/data_fetchers/fetch_runpod.py > /tmp/our-fetch-runpod.py

# 3. Manually port our availability filtering to new structure
# 4. Test thoroughly!
```

**2. Controller Server Logic** 🔴 HIGH PRIORITY
```bash
# Check conflicts
git diff sky/jobs/server/core.py
git diff sky/serve/server/impl.py

# Strategy:
# - We added inject_controller_image_config() calls
# - Upstream likely changed controller initialization
# - Need to preserve both

# For each file:
# 1. Accept upstream as base
# 2. Add our inject_controller_image_config() calls in appropriate places
# 3. Ensure our calls happen after config is loaded but before submission
```

**3. Kubernetes Instance Provisioning** 🔴 HIGH PRIORITY
```bash
# Check conflict
git diff sky/provision/kubernetes/instance.py

# Strategy:
# - We added evicted pod filtering
# - Upstream may have pod handling improvements
# - Merge both

# Manual merge steps:
# 1. Review both versions
# 2. Keep upstream improvements
# 3. Add our evicted pod filter to their pod listing logic
# 4. Update tests if needed
```

**4. Controller Utils** 🟡 MEDIUM PRIORITY
```bash
# Check conflict
git diff sky/utils/controller_utils.py

# Strategy:
# - We added better error handling and shlex.quote()
# - Upstream may have fixed same issues
# - Check if upstream has our fixes

# If upstream has our fixes:
git checkout --theirs sky/utils/controller_utils.py

# Otherwise:
# Manually merge our error handling improvements
```

**5. Controller Templates** 🟡 MEDIUM PRIORITY
```bash
# Check conflicts
git diff sky/templates/jobs-controller.yaml.j2
git diff sky/templates/sky-serve-controller.yaml.j2

# Strategy:
# - We changed /home/sky to $HOME
# - We added shlex.quote() for packages
# - Upstream may have template improvements
# - Merge both

# Manual merge for each template
```

**6. Common Utils** 🟢 LOW RISK
```bash
# Check conflict (if any)
git diff sky/utils/common_utils.py

# Strategy:
# - We added inject_controller_image_config() function
# - Upstream likely modified other parts
# - Should auto-merge, but verify

# If conflict:
# - Keep both our new function and upstream changes
# - They should not overlap
```

**7. Serve Service** 🟢 LOW RISK
```bash
# Check conflict (if any)
git diff sky/serve/service.py

# Strategy:
# - We added orphaned replica cleanup
# - Upstream may have service improvements
# - Merge both

# If conflict:
# - Keep our cleanup logic
# - Integrate with upstream changes
```

**8. Existing Custom Features**
```bash
# CloudWatch logging
git diff sky/logs/aws.py
# Strategy: Usually auto-merges; verify our graceful degradation logic

# Cudo Python 3.10
git diff sky/clouds/cudo.py
# Strategy: Check if upstream fixed; otherwise keep ours

# RunPod cloud
git diff sky/clouds/runpod.py
# Strategy: Merge our availability logic with upstream fixes
```

#### Phase 4: Verification & Testing (3-5 hours)

```bash
# After resolving all conflicts
git status  # Should show no conflicts

# 7. Install dependencies
make install

# 8. Run tests
make test 2>&1 | tee /tmp/test-upgrade-v0.11.1.log

# 9. Compare with baseline
# Check if new test failures appeared
# Expected: similar or fewer failures than v0.10.5

# 10. Manual verification of custom features
```

**Test Checklist:**
- [ ] `make install` completes without errors
- [ ] `make test` passes (or similar failures to baseline)
- [ ] Custom catalog URLs work (`SKYPILOT_CATALOG_BASE_URL`)
- [ ] Controller image override works (`SKYPILOT_CONTROLLER_IMAGE`)
- [ ] CloudWatch logging works (controller-only, graceful degradation)
- [ ] RunPod availability filtering works
- [ ] Kubernetes evicted pods are ignored
- [ ] Serve orphaned replica cleanup works
- [ ] Cudo works on Python 3.10
- [ ] Controller dependency installation handles version specifiers
- [ ] `sky check` shows all expected clouds
- [ ] No import errors

#### Phase 5: Commit & Integration (30 minutes)

```bash
# 11. Review all changes
git diff --stat v0.11.1..HEAD
git diff --name-only v0.11.1..HEAD | sort

# 12. Commit the merge
git add .
git commit -m "Merge v0.11.1: integrate upstream changes

Integrated 208 commits from v0.10.5 to v0.11.1 with our custom features.

Custom features preserved:
- Controller image override via SKYPILOT_CONTROLLER_IMAGE (#17, #18)
- Controller dependency installation fixes (#14, #19, #20)
- Kubernetes evicted pods handling (#21)
- Serve orphaned replica cleanup (#15)
- Custom catalog URLs (from v0.10.5)
- CloudWatch logging enhancements (from v0.10.5)
- RunPod availability filtering (from v0.10.5)
- Cudo Python 3.10 compatibility (from v0.10.5)

Major upstream improvements:
- RunPod catalog fetcher refactor
- Controller environment variable fixes
- SkyServe resource management improvements
- GCP B200 GPU support
- Transaction write operation fixes

Conflicts resolved: [COUNT]
Tests: [PASSED/FAILED] (baseline: [BASELINE])

Co-authored-by: Claude <noreply@anthropic.com>
"

# 13. Tag the new base version
git tag -a ojin-base-v0.11.1 -m "Base upstream version v0.11.1"

# 14. Review before merging to main
git log --graph --oneline -10
git diff v0.10.5..HEAD --stat | head -50
```

#### Phase 6: Merge to Main Branch (15 minutes)

```bash
# 15. Merge to ojin-release
git checkout ojin-release
git merge upgrade/v0.11.1-merge --ff-only

# If fast-forward not possible, create merge commit
git merge upgrade/v0.11.1-merge --no-ff -m "Upgrade to v0.11.1"

# 16. Push to remote
git push origin ojin-release
git push origin ojin-base-v0.11.1
git push origin upgrade/v0.11.1-merge  # Keep for reference

# 17. Verify remote state
git log --oneline -5
```

#### Phase 7: Update Documentation (30 minutes)

```bash
# 18. Update CUSTOM_CHANGES.md
# - Update "Last Updated" date
# - Update "Base Version" to v0.11.1
# - Add new section in "Version History"
# - Note any removed/replaced features

# 19. Update UPGRADE_PROCESS.md
# - Add lessons learned from this upgrade
# - Update statistics

# 20. Create PR or deployment
# - Follow team's deployment process
# - Update any deployment configurations
# - Notify team of upgrade
```

## Conflict Resolution Decision Tree

```
For each conflicted file:

1. Is it our custom infrastructure (.github, Dockerfile, Makefile, fork/)?
   ├─ YES → Keep ours (--ours)
   └─ NO → Continue...

2. Is it dependencies.py?
   ├─ Check if upstream has our pins → Accept theirs
   ├─ Upstream missing our pins → Manual merge
   └─ NO → Continue...

3. Is it RunPod catalog fetcher?
   ├─ YES → Accept upstream, then port our availability filtering
   └─ NO → Continue...

4. Is it controller-related (jobs/server/core.py, serve/server/impl.py)?
   ├─ YES → Accept upstream, then add our inject_controller_image_config() calls
   └─ NO → Continue...

5. Is it Kubernetes instance.py?
   ├─ YES → Merge both: upstream improvements + our evicted pod filtering
   └─ NO → Continue...

6. Is it controller templates or utils?
   ├─ YES → Merge both: upstream improvements + our fixes
   └─ NO → Continue...

7. Is it existing custom features from v0.10.5?
   ├─ Check if upstream has same fix → Accept theirs
   ├─ Upstream doesn't have fix → Keep ours or merge manually
   └─ Can both coexist? → Merge both manually
```

## Files Requiring Special Attention

### 🔴 CRITICAL - Manual Merge Required

1. **`sky/catalog/data_fetchers/fetch_runpod.py`**
   - Upstream: 698 line refactor
   - Ours: Availability filtering
   - Action: Port our logic to new structure

2. **`sky/jobs/server/core.py`**
   - Upstream: Controller improvements
   - Ours: Added `inject_controller_image_config()` call
   - Action: Merge both

3. **`sky/serve/server/impl.py`**
   - Upstream: Controller improvements
   - Ours: Added `inject_controller_image_config()` call
   - Action: Merge both

4. **`sky/provision/kubernetes/instance.py`**
   - Upstream: K8s improvements
   - Ours: Evicted pod filtering
   - Action: Merge both

### 🟡 HIGH PRIORITY - Review Carefully

5. **`sky/utils/controller_utils.py`**
   - Check if upstream fixed our issues
   - Merge if needed

6. **`sky/templates/jobs-controller.yaml.j2`**
   - Merge template changes

7. **`sky/templates/sky-serve-controller.yaml.j2`**
   - Merge template changes

8. **`sky/clouds/runpod.py`**
   - Merge availability logic with upstream

### 🟢 STANDARD - Follow Patterns

9. **`sky/logs/aws.py`** - CloudWatch (should auto-merge)
10. **`sky/clouds/cudo.py`** - Python 3.10 compat (check if upstream fixed)
11. **`sky/serve/service.py`** - Orphaned replicas (should auto-merge)
12. **`sky/utils/common_utils.py`** - New function (should auto-merge)
13. **`sky/catalog/catalog_url_config.py`** - Keep ours (no upstream changes)

## Rollback Plan

If the upgrade fails or introduces critical bugs:

```bash
# Option 1: Reset ojin-release to backup
git checkout ojin-release
git reset --hard backup-ojin-release-before-v0.11.1-upgrade
git push origin ojin-release --force-with-lease

# Option 2: Keep upgrade branch for debugging
git checkout ojin-release
git branch -d upgrade/v0.11.1-merge  # Delete after fixing

# Option 3: Incremental rollback
git revert <merge-commit-hash>
git push origin ojin-release
```

## Post-Upgrade Tasks

### Immediate (Day 1)

- [ ] Update `fork/CUSTOM_CHANGES.md` with v0.11.1 details
- [ ] Update `fork/UPGRADE_PROCESS.md` with lessons learned
- [ ] Test all custom features in staging environment
- [ ] Verify container builds work
- [ ] Run smoke tests on key clouds (RunPod, K8s, AWS)

### Short-term (Week 1)

- [ ] Monitor for issues in production
- [ ] Update deployment documentation
- [ ] Train team on any new features from v0.11.1
- [ ] Consider upstreaming our fixes:
  - Evicted pods handling
  - Controller dependency installation improvements
  - Orphaned replica cleanup

### Long-term (Month 1)

- [ ] Evaluate if upstream added similar features to ours
- [ ] Clean up any deprecated code
- [ ] Performance testing and optimization
- [ ] Documentation updates

## Expected Outcome

**Success Criteria:**
- ✅ Base version: v0.11.1 (208 new commits)
- ✅ All 9 custom commits (#13-22) preserved
- ✅ All custom features from v0.10.5 preserved
- ✅ RunPod availability filtering integrated with new fetcher
- ✅ Controller image override working
- ✅ Kubernetes evicted pods handled
- ✅ No regressions in test suite
- ✅ Clean git history

**Statistics Target:**
- Time: 6-10 hours (including testing)
- Conflicts: ~20-30 files (estimate)
- Test failures: ≤ baseline (same as pre-upgrade)
- Success rate: 100% (no regressions)

## Key Differences from v0.10.5 Upgrade

**Similarities:**
- ✅ Use three-way merge strategy (proven successful)
- ✅ Same conflict categorization approach
- ✅ Extensive testing before commit
- ✅ Backup and rollback plan

**Differences:**
- ⚠️ More controller-related conflicts (we added features)
- ⚠️ RunPod has major refactor (not just fixes)
- ⚠️ We have more K8s customizations now
- ✅ Better documented custom changes (CUSTOM_CHANGES.md)
- ✅ More experience with merge strategy

## Timeline Estimate

| Phase | Task | Time | Cumulative |
|-------|------|------|------------|
| 1 | Preparation & Backup | 10 min | 10 min |
| 2 | Initiate Merge | 2 min | 12 min |
| 3a | Category A/B Conflicts | 30 min | 42 min |
| 3b | RunPod Catalog Fetcher | 1-2 hours | 2h 42min |
| 3c | Controller Logic | 1 hour | 3h 42min |
| 3d | Other Manual Merges | 1 hour | 4h 42min |
| 4 | Testing & Verification | 3-5 hours | 7-9h 42min |
| 5 | Commit & Integration | 30 min | 8-10h 12min |
| 6 | Merge to Main | 15 min | 8-10h 27min |
| 7 | Documentation | 30 min | 9-11 hours |

**Total Estimate:** 9-11 hours (full day)

## Risk Mitigation

1. **RunPod Refactor Risk:**
   - Create separate branch to test RunPod integration
   - Test with real RunPod API before committing
   - Have rollback plan for RunPod specifically

2. **Controller Conflicts:**
   - Test controller creation in K8s cluster
   - Verify `SKYPILOT_CONTROLLER_IMAGE` still works
   - Test dependency installation with complex packages

3. **Kubernetes Changes:**
   - Test with pods that get evicted
   - Verify our filter logic is preserved
   - Test provision/termination flows

4. **Testing Time:**
   - Allocate full day for upgrade
   - Don't rush the testing phase
   - Compare test results with baseline

## Quick Reference Commands

```bash
# Start upgrade
git checkout ojin-release
git branch backup-ojin-release-before-v0.11.1-upgrade
git push origin backup-ojin-release-before-v0.11.1-upgrade
git checkout -b upgrade/v0.11.1-merge
git merge v0.11.1 --no-commit --no-ff

# Check conflicts
git status --short | grep "^[UA][UA]"

# Accept upstream
git checkout --theirs <file> && git add <file>

# Keep ours
git checkout --ours <file> && git add <file>

# List our custom files
git diff v0.10.5..HEAD --name-only | sort

# Test
make install && make test

# Commit
git add .
git commit  # Use detailed message above

# Tag and merge
git tag -a ojin-base-v0.11.1 -m "Base upstream version v0.11.1"
git checkout ojin-release
git merge upgrade/v0.11.1-merge --ff-only
git push origin ojin-release ojin-base-v0.11.1 upgrade/v0.11.1-merge

# Rollback if needed
git reset --hard backup-ojin-release-before-v0.11.1-upgrade
```

## Success Metrics

Track these metrics to evaluate upgrade success:

1. **Merge Quality:**
   - Number of conflicts vs. estimate
   - Time spent resolving conflicts
   - Number of merge iterations needed

2. **Test Results:**
   - Test pass rate vs. baseline
   - New test failures introduced
   - Custom feature test coverage

3. **Deployment:**
   - Time to production
   - Issues found in staging
   - Rollback needed? (target: no)

4. **Feature Preservation:**
   - All custom features working
   - No performance regressions
   - User-facing changes documented

## Contact & Support

For questions during upgrade:
1. Review this strategy document
2. Check `fork/CUSTOM_CHANGES.md` for feature details
3. Check `fork/UPGRADE_PROCESS.md` for process guidance
4. Review git history: `git log --grep="Merge v0.10"`
5. Compare with v0.10.5 upgrade: `fork/UPGRADE_STRATEGY_v0.10.5.md`

---

**Remember:**
- Take your time with manual merges
- Test thoroughly before committing
- Document any deviations from this plan
- Update this document with lessons learned after completion
- The merge strategy is safer than rebase - use it confidently!

**Good luck with the upgrade!** 🚀
