# Custom Changes Tracking

**Purpose:** Track all intentional modifications to the SkyPilot codebase for easier upgrades.

**Last Updated:** 2025-12-03
**Base Version:** v0.10.5

---

## 🤖 AI Agent Instructions

**When to Update This File:**
- After completing an upgrade
- When adding a new custom feature
- When removing/replacing a custom feature

**How to Update:**

1. **Verify current state matches git history:**
   ```bash
   # Get base version
   BASE_VERSION=$(git describe --tags --abbrev=0 ojin-release | grep -o 'v0\.10\.[0-9]*')

   # List custom commits
   git log $BASE_VERSION..HEAD --oneline

   # List modified files
   git diff $BASE_VERSION..HEAD --name-only | sort
   ```

2. **Update the file:**
   - Add any new custom features under "Custom Features"
   - Update file paths if files moved
   - Mark features as "REPLACED" if upstream has them
   - Update "Version History" section with upgrade details
   - Update "Last Updated" and "Base Version" at top

3. **Validate consistency:**
   ```bash
   # Run validation script
   ./fork/validate-changes.sh
   ```

**Template for New Custom Feature:**
```markdown
### N. Feature Name 🟢/🟡/🔵 CATEGORY

**Description:** Brief description

**Commits:**
- `<hash>` - commit message

**Files:**
- `path/to/file.py` 🟢/🟡 (status)
  - What changed

**Changes:**
\`\`\`python
# Code example showing the change
\`\`\`

**Merge Strategy:**
- How to handle during upgrades

**Test:** How to verify it works
```

---

---

## Change Categories

### 🟢 KEEP ALWAYS (Category A)
Files we always want to preserve during upgrades.

### 🟡 MERGE CAREFULLY (Category B)
Files where we have custom logic that must be integrated with upstream changes.

### 🔵 REVIEW & DECIDE (Category C)
Features we added that might be in upstream now - check each upgrade.

---

## Custom Features

### Custom Catalog URLs 🟢 KEEP ALWAYS

**Description:** Allow overriding catalog URLs via environment variables for custom cloud deployments.

**Files:**
- `sky/catalog/catalog_url_config.py` 🟢 (our file, always keep)

**Environment Variables:**
- `SKYPILOT_CATALOG_BASE_URL` - Global override
- `SKYPILOT_<CLOUD>_CATALOG_URL` - Per-cloud override

**Integration Points:**
- Used by catalog fetchers when downloading cloud pricing/availability data

**Merge Strategy:**
- Always keep our version
- Check if upstream added similar functionality

**Test:** Set env var and verify custom URL is used

---

### CloudWatch Logging Enhancements 🟡 MERGE CAREFULLY

**Description:** Graceful degradation and controller-only logging for AWS CloudWatch.

**Commits:**
- `e69d07288` - feat(logs): graceful degradation and controller-only CloudWatch logging
- `1a98e2c93` - fix: disable external logging on replicas

**Files:**
- `sky/logs/aws.py` 🟡 (modified)
  - Added `apply_to: controller_only` config option
  - Changed ERROR → WARNING when AWS credentials unavailable
  - Exit 0 instead of error when creds missing

**Changes:**
```python
# Before (upstream):
if not credentials_available:
    logger.error("AWS credentials not available")
    sys.exit(1)

# After (ours):
if not credentials_available:
    logger.warning("AWS credentials not available - skipping CloudWatch")
    sys.exit(0)  # Graceful degradation
```

**Merge Strategy:**
- Usually auto-merges successfully
- Verify our graceful degradation logic is preserved
- Check `apply_to: controller_only` config still works

**Test:** Run without AWS credentials, should warn but not error

---

### RunPod Availability Filtering 🟡 MERGE CAREFULLY

**Description:** Only show actually available GPU instances in catalog.

**Commits:**
- `a69bd7c94` - fix(runpod): use regional availability
- Part of `90d513d4c` - feat: improve RunPod availability checking

**Files:**
- `sky/clouds/runpod.py` 🟡 (modified)
  - Enhanced `regions_with_offering()` to check actual availability
  - Added GPU ID mapping
- `sky/catalog/data_fetchers/fetch_runpod.py` 🟡 (modified)
  - Filter catalog to only available resources

**Changes:**
```python
# Added availability checking in regions_with_offering()
def regions_with_offering(...):
    # Check actual API availability
    available_regions = runpod_utils.get_available_regions(accelerator)
    return available_regions
```

**Integration Points:**
- Uses `sky/provision/runpod/utils.py` for GPU_NAME_MAP
- Calls RunPod API for real-time availability

**Merge Strategy:**
- Merge our availability logic with upstream volume/check fixes
- Upstream had fixes in commits:
  - `d56bac264` - Fix runpod check + redact API URL
  - `0807f15e3` - Fix Runpod Volumes ls
- Keep our availability filtering, integrate their fixes

**Test:** Check `sky show-gpus --cloud runpod` only shows available

---

### Serve Orphaned Replica Cleanup 🟡 MERGE CAREFULLY

**Description:** Fix bug where orphaned replica records are not cleaned from the database during `sky serve down`.

**Commits:**
- `TBD` - fix: clean up orphaned replica records during serve down

**Files:**
- `sky/serve/service.py` 🟡 (modified)
  - Added `serve_state.remove_replica()` call when cluster doesn't exist

**Changes:**
```python
# Before (upstream):
for info in replica_infos:
    if info.cluster_name not in existing_cluster_names:
        logger.info(f'Cluster {info.cluster_name} for replica '
                    f'{info.replica_id} not found. Might be a failed '
                    'cluster. Skipping.')
        continue  # BUG: replica left in database

# After (ours):
for info in replica_infos:
    if info.cluster_name not in existing_cluster_names:
        logger.info(f'Cluster {info.cluster_name} for replica '
                    f'{info.replica_id} not found. Might be a failed '
                    'cluster. Removing replica from database.')
        serve_state.remove_replica(service_name, info.replica_id)  # FIX
        continue
```

**Problem:**
When a replica's cluster doesn't exist (failed launch, manually deleted, etc.), the `_cleanup()` function logs "Skipping" but never removes the replica record from the database. This causes stale replicas to appear when reusing a service name.

**Merge Strategy:**
- Check if upstream fixed this bug
- If yes: accept upstream
- If no: keep our fix
- This is a clear bug fix, likely acceptable upstream

**Test:**
1. Create a service with replicas
2. Have some replicas fail (cluster doesn't exist)
3. `sky serve down` the service
4. `sky serve up` with same name
5. Verify no old replicas are visible

---

### Cudo Python 3.10 Compatibility 🟡 MERGE CAREFULLY

**Description:** Support both old and new Cudo SDK package names for Python 3.10.

**Commits:**
- `6871e1818` - fix: restore cudo sdk compatibility with Python 3.10
- Part of `90d513d4c`

**Files:**
- `sky/clouds/cudo.py` 🟡 (modified)
  - Added `_load_cudo_api_module()` function
  - Tries multiple import paths for Cudo SDK

**Changes:**
```python
def _load_cudo_api_module():
    """Returns the Cudo API module and its ApiException."""
    candidates = (
        ('cudo_compute.cudo_api', 'cudo_compute.rest'),
        ('cudo_api', 'cudo_api.rest'),  # Fallback for older SDK
    )
    for module_path, rest_module_path in candidates:
        try:
            module = importlib.import_module(module_path)
            # ... return if successful
        except ImportError:
            continue
```

**Merge Strategy:**
- Check if upstream fixed Python 3.10 compatibility
- If yes: accept upstream
- If no: keep our fix
- v0.10.5: Kept our version

**Test:** Install on Python 3.10, verify Cudo imports work

---

### Seeweb Provider 🔵 REVIEW & DECIDE

**Description:** Support for Seeweb cloud provider.

**Commits:**
- Part of `90d513d4c` - feat: add Seeweb provider

**Status:** **REPLACED BY UPSTREAM in v0.10.5**

**Files** (now using upstream):
- `sky/adaptors/seeweb.py`
- `sky/catalog/data_fetchers/fetch_seeweb.py`
- `sky/catalog/seeweb_catalog.py`
- `sky/clouds/seeweb.py`
- `sky/provision/seeweb/`
- `sky/templates/seeweb-ray.yml.j2`

**Upstream Integration:**
- v0.10.5 added official Seeweb support:
  - `d9f7c5b0e` - Add Seeweb Provider
  - `44fa087e8` - Use consistent L40S GPU name for seeweb
  - `59773bc2e` - Seeweb Docs / Snapshot Update 01

**Merge Strategy:**
- ✅ Accept upstream implementation (better maintained)
- Delete our cherry-picked version
- Test Seeweb still works with upstream code

**Test:** Provision a Seeweb instance

---

## Infrastructure Customizations 🟢 KEEP ALWAYS

### Custom CI/CD

**Files:**
- `.github/workflows/*.yml` 🟢 (modified)
  - Custom build workflows
  - ECR publishing
  - Version tagging
- `_github/` 🟢 (renamed)
  - Disabled upstream CI by moving to `_github/`

**Merge Strategy:** Always keep our workflows

---

### Development Environment

**Files:**
- `.devcontainer/devcontainer.json` 🟢 (our file)
  - Custom DevContainer setup
  - Python 3.10 environment
  - Pre-configured tools
- `Dockerfile` 🟢 (modified)
  - Custom base image
  - Additional tools
- `Dockerfile_debug` 🟢 (our file)
  - Debug-specific build
- `Makefile` 🟢 (our file)
  - Development shortcuts
  - Test commands

**Merge Strategy:** Always keep ours

---

### Fork Documentation

**Files:**
- `fork/` 🟢 (our directory)
  - `WORKFLOW.md`
  - `CUSTOMIZATIONS.md`
  - `UPGRADE_PROCESS.md`
  - `CUSTOM_CHANGES.md` (this file)
  - `upgrade-helper.sh`
  - `UPGRADE_STRATEGY_v0.10.5.md`
- `CLAUDE.md` 🟢 (our file)
  - AI assistant guidelines
- `requirements-dev.txt` 🟡 (modified)
  - Additional dev dependencies

**Merge Strategy:**
- Fork docs: always keep
- requirements-dev.txt: merge with upstream additions

---

## Removed/Replaced Features

### Features Now in Upstream

1. **Seeweb Support** - Replaced in v0.10.5
   - Our implementation: custom cherry-pick
   - Upstream: official provider with docs
   - Action: Accepted upstream version

---

## Merge Patterns by File Type

### Python Files

**Always Keep Ours:**
- `sky/catalog/catalog_url_config.py`

**Merge Carefully:**
- `sky/logs/aws.py` - CloudWatch logging
- `sky/clouds/runpod.py` - Availability filtering
- `sky/clouds/cudo.py` - Python 3.10 compat
- `sky/serve/service.py` - Orphaned replica cleanup

**Usually Accept Theirs:**
- `sky/__init__.py` - Just add new cloud imports
- `sky/clouds/__init__.py` - Add new cloud classes
- `sky/provision/__init__.py` - Add new provisioners
- `sky/backends/backend_utils.py` - Add new auth handlers

### Test Files

**Keep Ours:**
- Tests for custom features (catalog URLs, etc.)

**Accept Theirs:**
- General test updates
- New cloud provider tests
- Framework updates

**Merge:**
- Tests that cover both custom and upstream changes

### Documentation

**Keep Ours:**
- `fork/*`
- `CLAUDE.md`
- Custom sections in `README.md`

**Accept Theirs:**
- `docs/` - Upstream documentation
- Most of `README.md`
- `CONTRIBUTING.md`

### Configuration

**Keep Ours:**
- `.github/workflows/`
- `.devcontainer/`
- `Makefile`
- `Dockerfile*`

**Merge:**
- `requirements-dev.txt` - Add both sets of dependencies
- `.gitignore` - Merge both

**Accept Theirs:**
- `sky/setup_files/dependencies.py`
- `setup.py`
- Most `pyproject.toml` changes

---

## Upgrade Checklist

When upgrading to a new version:

- [ ] Review this file before starting
- [ ] Check if any "REVIEW & DECIDE" features are now in upstream
- [ ] Run upgrade helper script
- [ ] Resolve conflicts using patterns above
- [ ] Test all custom features:
  - [ ] Custom catalog URLs
  - [ ] CloudWatch logging (controller-only)
  - [ ] RunPod availability filtering
  - [ ] Serve orphaned replica cleanup
  - [ ] Cudo on Python 3.10
  - [ ] Seeweb (using upstream)
- [ ] Update this file with new version and changes
- [ ] Update `fork/CUSTOMIZATIONS.md` if features changed
- [ ] Add lessons learned to `fork/UPGRADE_PROCESS.md`

---

## Version History

### v0.10.5 (2025-11-22)

**Merged:** 488 commits from v0.10.3.post2 → v0.10.5

**Changes:**
- ✅ Accepted upstream Seeweb implementation
- ✅ Preserved CloudWatch logging enhancements
- ✅ Preserved RunPod availability filtering
- ✅ Preserved Cudo Python 3.10 compatibility
- ✅ Integrated upstream RunPod volume fixes
- ➕ Added Shadeform cloud (upstream)
- ➕ Added PrimeIntellect cloud (upstream)

**Conflicts:** 24 files, all resolved
**Tests:** 1 failure (pre-existing, not a regression)
**Time:** ~5 hours

**Lessons:**
- Merge strategy works much better than rebase
- Auto-merge handled most customizations correctly
- Accepting upstream Seeweb reduced maintenance
- Need to run `make install` before testing

---

### v0.10.3.post2 (Base)

**Initial Fork Features:**
- Custom catalog URLs
- RunPod catalog fetcher
- Seeweb provider (later replaced by upstream)
- Cudo Python 3.10 compatibility
- CloudWatch logging enhancements
- Custom CI/CD workflows

---

## Quick Reference

```bash
# Find our custom changes
git diff v0.10.5..HEAD --stat

# Check specific feature
git log --all --grep="catalog URL" --oneline
git log --all --grep="CloudWatch" --oneline

# See files we've modified
git diff v0.10.5..HEAD --name-only | sort | uniq

# Check if feature in upstream
git log v0.10.5 --grep="feature-name" --oneline
```

---

## Contact

For questions about custom changes:
1. Check this file first
2. Review git history: `git log --all --grep="<feature>"`
3. Check related PR/commit messages
4. Review `fork/UPGRADE_PROCESS.md` for process

---

**Remember:** Keep this file updated after each upgrade!
