# RunPod Availability Filtering Restoration Guide

**Purpose:** Re-add regional availability filtering to RunPod catalog fetcher after v0.11.1 upgrade

**Context:** During the v0.11.1 upgrade, we accepted upstream's major refactor of `sky/catalog/data_fetchers/fetch_runpod.py` (698 lines) which added CPU support but removed our custom regional availability filtering. This guide provides step-by-step instructions to restore this feature.

---

## Background

### What Was Removed

In v0.10.5, we added filtering to only include GPU instances with actual stock availability in specific regions. This prevented users from seeing GPUs in the catalog that weren't actually available for provisioning.

**Key Features:**
- `filter_available` parameter (default: True)
- Regional stock status checking via RunPod API
- `--no-filter-available` CLI flag for debugging
- Only include instances where `stockStatus` is not "Unavailable"

### Why It Was Removed

Upstream v0.11.1 completely refactored the catalog fetcher:
- Added CPU instance support
- Changed query structure
- Simplified `get_gpu_instance_configurations()` function
- Removed regional availability checking

**Decision:** During upgrade, we accepted upstream's refactor to get the benefits of their improvements (CPU support, better structure). We documented that filtering would be re-added in a follow-up.

---

## Current State (v0.11.1)

### File: `sky/catalog/data_fetchers/fetch_runpod.py`

**Current Behavior:**
- Fetches ALL GPU instances regardless of availability
- Shows instances even if they have zero stock in all regions
- No filtering based on `stockStatus`

**Function Structure:**
```python
def get_gpu_instance_configurations(gpu_id: str) -> List[Dict[str, Any]]:
    """Retrieves available GPU instance configurations for a given GPU ID.

    Currently returns ALL instances for all regions, regardless of stock.
    """
    instances = []
    detailed_gpu_1 = get_gpu_details(gpu_id, gpu_count=1)
    base_gpu_name = format_gpu_name(detailed_gpu_1)

    # ... get max GPU count ...

    for gpu_count in range(1, int(max_gpu_count) + 1):
        detailed_gpu = get_gpu_details(gpu_id, gpu_count)

        # Only add secure clouds
        if not detailed_gpu['secureCloud']:
            continue

        gpu_info = get_gpu_info(base_gpu_name, detailed_gpu, gpu_count)
        if gpu_info is None:
            continue

        # Get pricing
        spot_price = base_price = None
        if detailed_gpu['secureSpotPrice'] is not None:
            spot_price = format_price(detailed_gpu['secureSpotPrice'] * gpu_count)
        if detailed_gpu['securePrice'] is not None:
            base_price = format_price(detailed_gpu['securePrice'] * gpu_count)

        # ADD ALL REGIONS WITHOUT CHECKING AVAILABILITY
        for region, zones in REGION_ZONES.items():
            for zone in zones:
                instances.append({
                    'InstanceType': f'{gpu_count}x_{base_gpu_name}_SECURE',
                    'AcceleratorName': base_gpu_name,
                    'AcceleratorCount': float(gpu_count),
                    'SpotPrice': spot_price,
                    'Price': base_price,
                    'Region': region,
                    'AvailabilityZone': zone,
                    **gpu_info
                })

    return instances
```

---

## Previous Implementation (v0.10.5)

### Location: `/tmp/our-fetch-runpod.py` (saved during upgrade)

**Key Components:**

1. **GraphQL Query for Regional Availability:**
```python
LOWEST_PRICE_BY_REGION_QUERY = """
    query LowestPriceByRegion {{
      gpuTypes(input: {{id: "{gpu_id}"}}) {{
        lowestPrice(input: {{
          gpuCount: {gpu_count},
          countryCode: "{country_code}"
        }}) {{
          stockStatus
          availableGpuCounts
          maxUnreservedGpuCount
        }}
      }}
    }}"""
```

2. **Region to Country Code Mapping:**
```python
REGION_COUNTRY_CODES = {
    'EU-RO-1': 'RO',  # Romania
    'EUR-IS-1': 'IS',  # Iceland
    'EUR-IS-2': 'IS',  # Iceland
    # ... etc
}

STOCK_UNAVAILABLE = 'Unavailable'
```

3. **Regional Availability Check:**
```python
@lru_cache(maxsize=128)
def get_lowest_price_by_region(gpu_id: str, gpu_count: int,
                                country_code: str) -> Dict[str, Any]:
    """Query RunPod API for lowest price and stock in specific region."""
    query = LOWEST_PRICE_BY_REGION_QUERY.format(
        gpu_id=gpu_id,
        gpu_count=gpu_count,
        country_code=country_code
    )
    result = graphql.run_graphql_query(query)

    if 'errors' in result:
        raise RuntimeError(f"GraphQL query failed: {result['errors']}")

    gpu_types = result.get('data', {}).get('gpuTypes', [])
    if not gpu_types:
        raise ValueError(f"No GPU types found for gpu_id={gpu_id}")

    return gpu_types[0].get('lowestPrice', {})
```

4. **Filtering Logic in `get_instance_configurations()`:**
```python
def get_instance_configurations(gpu_id: str,
                                filter_available: bool = True) -> List[Dict]:
    """Generate instance configurations for a GPU type.

    Args:
        gpu_id: RunPod GPU ID
        filter_available: If True, skip GPUs with no stock availability
    """
    instances = []
    # ... setup code ...

    for gpu_count in range(1, int(max_gpu_count) + 1):
        # ... get GPU details ...

        for region, zones in REGION_ZONES.items():
            region_stock_status = global_stock_status

            # CHECK REGIONAL AVAILABILITY
            if filter_available:
                country_code = REGION_COUNTRY_CODES.get(region)
                if country_code:
                    try:
                        regional_lowest = get_lowest_price_by_region(
                            gpu_id, gpu_count, country_code)
                        region_stock_status = (
                            regional_lowest.get('stockStatus') or
                            STOCK_UNAVAILABLE)
                    except (ValueError, RuntimeError,
                            requests.exceptions.RequestException, TimeoutError):
                        logging.exception(
                            'Regional availability unavailable for gpu_id=%s '
                            'gpu_count=%d country_code=%s', gpu_id, gpu_count,
                            country_code)
                        region_stock_status = STOCK_UNAVAILABLE

                # SKIP IF UNAVAILABLE
                if region_stock_status in (None, STOCK_UNAVAILABLE):
                    continue

            # Only add if available (or filtering disabled)
            for zone in zones:
                instances.append({...})

    return instances
```

5. **CLI Argument:**
```python
parser.add_argument(
    '--no-filter-available',
    action='store_true',
    help='Include all GPUs regardless of stock availability '
    '(default: filter out unavailable GPUs)',
)

# Usage
filter_available = not args.no_filter_available
```

---

## Step-by-Step Restoration Instructions

### Phase 1: Understand Current Structure (15 minutes)

1. **Read the current implementation:**
   ```bash
   cat sky/catalog/data_fetchers/fetch_runpod.py
   ```

2. **Identify key differences:**
   - Current version has `get_gpu_instance_configurations()` and `get_cpu_instance_configurations()`
   - Main function is `fetch_runpod_catalog(no_gpu: bool, no_cpu: bool)`
   - No `filter_available` parameter anywhere
   - GraphQL queries are for GPU details only, not regional availability

3. **Check if upstream added similar functionality:**
   ```bash
   git log v0.10.5..v0.11.1 --all --grep="availability\|stock" --oneline
   git log v0.10.5..v0.11.1 -- sky/catalog/data_fetchers/fetch_runpod.py --oneline
   ```

### Phase 2: Add Regional Availability Query (30 minutes)

**Location:** After existing GraphQL queries (around line 300)

**Task:** Add the regional availability query and helper function

```python
# After SECURE_CPU_TYPES_QUERY, add:

LOWEST_PRICE_BY_REGION_QUERY = """
    query LowestPriceByRegion {{
      gpuTypes(input: {{id: "{gpu_id}"}}) {{
        lowestPrice(input: {{
          gpuCount: {gpu_count},
          countryCode: "{country_code}"
        }}) {{
          stockStatus
          availableGpuCounts
          maxUnreservedGpuCount
        }}
      }}
    }}"""

# Region to country code mapping for availability checks
REGION_COUNTRY_CODES = {
    'EU-RO-1': 'RO',  # Romania
    'EUR-IS-1': 'IS',  # Iceland
    'EUR-IS-2': 'IS',  # Iceland
    'CA-MTL-1': 'CA',  # Canada - Montreal
    'CA-MTL-2': 'CA',  # Canada - Montreal
    'CA-MTL-3': 'CA',  # Canada - Montreal
    'US-GA-1': 'US',  # USA - Georgia
    'US-IL-1': 'US',  # USA - Illinois
    'US-KS-2': 'US',  # USA - Kansas
    'US-OR-1': 'US',  # USA - Oregon
    'US-TX-3': 'US',  # USA - Texas
}

STOCK_UNAVAILABLE = 'Unavailable'


def get_lowest_price_by_region(gpu_id: str, gpu_count: int,
                                country_code: str) -> Dict[str, Any]:
    """Query RunPod API for lowest price and stock status in a specific region.

    Args:
        gpu_id: RunPod GPU ID
        gpu_count: Number of GPUs
        country_code: ISO country code (e.g., 'US', 'RO')

    Returns:
        Dict with stockStatus, availableGpuCounts, maxUnreservedGpuCount

    Raises:
        ValueError: If GPU type not found
        RuntimeError: If GraphQL query fails
    """
    query = LOWEST_PRICE_BY_REGION_QUERY.format(
        gpu_id=gpu_id,
        gpu_count=gpu_count,
        country_code=country_code
    )

    result = graphql.run_graphql_query(query)

    if 'errors' in result:
        raise RuntimeError(f"GraphQL query failed: {result['errors']}")

    gpu_types = result.get('data', {}).get('gpuTypes', [])
    if not gpu_types:
        raise ValueError(f"No GPU types found for gpu_id={gpu_id}")

    return gpu_types[0].get('lowestPrice', {})
```

**Note:** You may need to add `from functools import lru_cache` at the top and add caching:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_lowest_price_by_region(...):
    # ... implementation
```

### Phase 3: Add Filtering to `get_gpu_instance_configurations()` (45 minutes)

**Current signature:**
```python
def get_gpu_instance_configurations(gpu_id: str) -> List[Dict[str, Any]]:
```

**New signature:**
```python
def get_gpu_instance_configurations(gpu_id: str,
                                   filter_available: bool = True) -> List[Dict[str, Any]]:
    """Retrieves available GPU instance configurations for a given GPU ID.

    Only secure cloud instances are included (community cloud instances
    are skipped). Each configuration includes pricing (spot and base), region,
    availabilityzone, and hardware details.

    Args:
        gpu_id (str): The identifier of the GPU type
        filter_available (bool): If True, only include instances with stock
            availability in specific regions. Default: True.

    Returns:
        List[Dict]: A list of dictionaries, each representing an instance
            configuration with the following keys:
                - 'InstanceType': String describing the instance type
                - 'AcceleratorName': Name of the GPU accelerator.
                - 'AcceleratorCount': Number of GPUs in the instance.
                - 'SpotPrice': Spot price for the instance (if available).
                - 'Price': Base price for the instance (if available).
                - 'Region': Cloud region.
                - 'AvailabilityZone': Availability zone within the region.
                - Additional hardware info (e.g., memory, vCPU) from GPU info.
    """
```

**Add filtering logic** in the region loop (around line 588-600):

```python
    for gpu_count in range(1, int(max_gpu_count) + 1):
        # ... existing code to get detailed_gpu and gpu_info ...

        # Get pricing (existing code)
        spot_price = base_price = None
        if detailed_gpu['secureSpotPrice'] is not None:
            spot_price = format_price(detailed_gpu['secureSpotPrice'] * gpu_count)
        if detailed_gpu['securePrice'] is not None:
            base_price = format_price(detailed_gpu['securePrice'] * gpu_count)

        # MODIFIED: Add regional availability filtering
        for region, zones in REGION_ZONES.items():
            region_stock_status = None  # Unknown by default

            if filter_available:
                # Get country code for this region
                country_code = REGION_COUNTRY_CODES.get(region)

                if country_code:
                    try:
                        # Query RunPod API for regional availability
                        regional_lowest = get_lowest_price_by_region(
                            gpu_id, gpu_count, country_code)
                        region_stock_status = (
                            regional_lowest.get('stockStatus') or
                            STOCK_UNAVAILABLE)
                    except (ValueError, RuntimeError, Exception) as e:
                        # Log warning but continue - fail-open approach
                        # Using print() since logger may not be available
                        print(f'Warning: Regional availability check failed for '
                              f'gpu_id={gpu_id} gpu_count={gpu_count} '
                              f'country_code={country_code}: {e}')
                        region_stock_status = STOCK_UNAVAILABLE
                else:
                    # No country code mapping - assume unavailable
                    region_stock_status = STOCK_UNAVAILABLE

                # Skip this region if stock is unavailable
                if region_stock_status in (None, STOCK_UNAVAILABLE):
                    continue

            # Add instances for all zones in this region
            for zone in zones:
                instances.append({
                    'InstanceType': f'{gpu_count}x_{base_gpu_name}_SECURE',
                    'AcceleratorName': base_gpu_name,
                    'AcceleratorCount': float(gpu_count),
                    'SpotPrice': spot_price,
                    'Price': base_price,
                    'Region': region,
                    'AvailabilityZone': zone,
                    **gpu_info
                })

    return instances
```

### Phase 4: Update `fetch_runpod_catalog()` Function (15 minutes)

**Current signature:**
```python
def fetch_runpod_catalog(no_gpu: bool, no_cpu: bool) -> pd.DataFrame:
```

**New signature:**
```python
def fetch_runpod_catalog(no_gpu: bool, no_cpu: bool,
                        filter_available: bool = True) -> pd.DataFrame:
    """Fetch and process RunPod GPU catalog data.

    Args:
        no_gpu: If True, skip GPU instances
        no_cpu: If True, skip CPU instances
        filter_available: If True, only include GPUs with stock availability.
            Default: True.

    Returns:
        DataFrame with catalog entries
    """
```

**Update the GPU fetching section:**

Find the line that calls `get_gpu_instance_configurations()` (around line 630):

```python
# OLD:
for gpu in gpus_to_fetch:
    logger.info(f'Fetching GPU: {gpu["displayName"]}...')
    configs = get_gpu_instance_configurations(gpu['id'])
    all_instances.extend(configs)

# NEW:
for gpu in gpus_to_fetch:
    logger.info(f'Fetching GPU: {gpu["displayName"]}...')
    configs = get_gpu_instance_configurations(gpu['id'],
                                              filter_available=filter_available)
    all_instances.extend(configs)
```

### Phase 5: Add CLI Argument (10 minutes)

**Location:** In `main()` function, after existing arguments (around line 680)

```python
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # ... existing arguments ...

    # ADD THIS:
    parser.add_argument(
        '--no-filter-available',
        action='store_true',
        help='Include all GPUs regardless of stock availability. '
             'By default, only GPUs with confirmed regional stock are included. '
             'Use this flag for debugging or to see the full catalog.',
    )

    args = parser.parse_args()

    # ... existing code ...

    # MODIFY THIS:
    filter_available = not args.no_filter_available

    df = fetch_runpod_catalog(
        no_gpu=args.no_gpu,
        no_cpu=args.no_cpu,
        filter_available=filter_available  # ADD THIS
    )
```

### Phase 6: Update Documentation (15 minutes)

**File: `sky/catalog/data_fetchers/fetch_runpod.py`**

Update the module docstring at the top:

```python
"""A script that generates the Runpod catalog.

Usage:
    python fetch_runpod.py [-h] [--output-dir OUTPUT_DIR] [--gpu-ids GPU_IDS]
                           [--no-gpu] [--no-cpu] [--no-filter-available]

The RUNPOD_API_KEY environment variable must be set with a valid read-access
RunPod API key.

Options:
    --gpu-ids: If provided, only fetches details for the specified GPU IDs
               (comma-separated). Otherwise, fetches all available GPUs.
               This flag is intended for testing and debugging.

    --no-filter-available: Include all GPUs regardless of stock availability.
                          By default, the script filters out GPUs with no
                          regional stock to prevent provisioning failures.
                          Use this for debugging or to see the full catalog.

Regional Availability Filtering:
    By default, this script queries the RunPod API for regional stock status
    and only includes GPU instances that are actually available. This prevents
    the catalog from showing GPUs that cannot be provisioned.

    The filtering is fail-open: if regional availability cannot be determined
    (e.g., API errors), the GPU is excluded from that region but the script
    continues processing other regions.
"""
```

### Phase 7: Testing (1-2 hours)

#### Unit Tests

**File: `tests/unit_tests/test_catalog.py`** (or create if doesn't exist)

Add test for availability filtering:

```python
def test_runpod_availability_filtering():
    """Test that RunPod catalog respects filter_available parameter."""
    from unittest import mock
    from sky.catalog.data_fetchers import fetch_runpod

    # Mock the GraphQL queries
    with mock.patch.object(fetch_runpod.graphql, 'run_graphql_query') as mock_query:
        # Setup mocks...

        # Test with filtering enabled
        configs_filtered = fetch_runpod.get_gpu_instance_configurations(
            'test-gpu-id', filter_available=True)

        # Test with filtering disabled
        configs_unfiltered = fetch_runpod.get_gpu_instance_configurations(
            'test-gpu-id', filter_available=False)

        # Unfiltered should have more instances
        assert len(configs_unfiltered) >= len(configs_filtered)
```

#### Manual Testing

1. **Test with filtering enabled (default):**
   ```bash
   cd /Users/runger/workspaces/journee/skypilot
   export RUNPOD_API_KEY="your-api-key"

   python sky/catalog/data_fetchers/fetch_runpod.py \
       --output-dir /tmp/runpod-test \
       --gpu-ids "NVIDIA GeForce RTX 4090"

   # Check output
   cat /tmp/runpod-test/vms.csv | grep "RTX 4090"
   # Should only show regions with actual stock
   ```

2. **Test with filtering disabled:**
   ```bash
   python sky/catalog/data_fetchers/fetch_runpod.py \
       --output-dir /tmp/runpod-test-unfiltered \
       --gpu-ids "NVIDIA GeForce RTX 4090" \
       --no-filter-available

   # Check output
   cat /tmp/runpod-test-unfiltered/vms.csv | grep "RTX 4090"
   # Should show ALL regions regardless of stock
   ```

3. **Compare results:**
   ```bash
   wc -l /tmp/runpod-test/vms.csv
   wc -l /tmp/runpod-test-unfiltered/vms.csv
   # Unfiltered should have more lines
   ```

4. **Test error handling:**
   ```bash
   # Test with invalid API key
   export RUNPOD_API_KEY="invalid"
   python sky/catalog/data_fetchers/fetch_runpod.py \
       --output-dir /tmp/runpod-test-error
   # Should fail gracefully with clear error message
   ```

5. **Integration test:**
   ```bash
   # Regenerate catalog
   python sky/catalog/data_fetchers/fetch_runpod.py \
       --output-dir sky/catalog/runpod/

   # Test with SkyPilot
   sky check
   sky show-gpus --cloud runpod
   # Should only show available GPUs
   ```

### Phase 8: Update CUSTOM_CHANGES.md (15 minutes)

**File: `fork/CUSTOM_CHANGES.md`**

Update the RunPod Availability Filtering section:

```markdown
### RunPod Availability Filtering 🟡 MERGE CAREFULLY

**Description:** Only show actually available GPU instances in catalog.

**Commits:**
- `a69bd7c94` - fix(runpod): use regional availability (#9) [v0.10.5]
- Part of `90d513d4c` - feat: improve RunPod availability checking [v0.10.5]
- `XXXXXXXX` - feat: restore RunPod availability filtering after v0.11.1 upgrade

**Status:** ✅ RESTORED after v0.11.1 upgrade

**Files:**
- `sky/catalog/data_fetchers/fetch_runpod.py` 🟡 (modified)
  - Added `filter_available` parameter (default: True)
  - Added `get_lowest_price_by_region()` query function
  - Added `REGION_COUNTRY_CODES` mapping
  - Filter catalog to only available resources per region
  - CLI flag `--no-filter-available` for debugging

**Changes:**
```python
def get_gpu_instance_configurations(gpu_id: str,
                                   filter_available: bool = True):
    """Generate GPU configs, optionally filtering by regional availability."""
    for region, zones in REGION_ZONES.items():
        if filter_available:
            # Query RunPod API for regional stock status
            country_code = REGION_COUNTRY_CODES.get(region)
            if country_code:
                regional_lowest = get_lowest_price_by_region(
                    gpu_id, gpu_count, country_code)
                region_stock_status = regional_lowest.get('stockStatus')

                # Skip if unavailable
                if region_stock_status in (None, 'Unavailable'):
                    continue

        # Add instances for available regions
        for zone in zones:
            instances.append({...})
```

**Integration Points:**
- Uses RunPod GraphQL API for stock status
- Integrates with upstream's new CPU support structure
- Fail-open approach: errors don't block entire catalog generation

**Merge Strategy:**
- Keep our filtering logic when merging future upstream changes
- Upstream may add similar functionality - compare and deduplicate if needed
- This is a value-add feature that reduces user friction

**Test:**
```bash
# With filtering (default)
python sky/catalog/data_fetchers/fetch_runpod.py --output-dir /tmp/test

# Without filtering
python sky/catalog/data_fetchers/fetch_runpod.py \
    --output-dir /tmp/test --no-filter-available

# Integration test
sky show-gpus --cloud runpod  # Should only show available GPUs
```
```

---

## Expected Outcome

After completing these steps:

✅ **Functionality:**
- RunPod catalog only shows GPUs with confirmed regional availability
- `--no-filter-available` flag allows seeing full catalog for debugging
- Fail-open behavior: API errors don't break catalog generation
- Works with upstream's CPU support

✅ **Performance:**
- LRU cache prevents redundant API calls
- ~30-60 second increase in catalog generation time (acceptable)
- Cached results improve subsequent runs

✅ **User Experience:**
- Users see only provisionable GPUs
- No more "GPU not available" errors after catalog shows it
- Especially important for high-demand GPUs (H100, L40S)

✅ **Compatibility:**
- Works with v0.11.1 upstream structure
- Preserves CPU instance support
- Integrates cleanly with existing code

---

## Troubleshooting

### Issue: GraphQL Query Fails

**Symptom:** `RuntimeError: GraphQL query failed`

**Solution:**
1. Check RunPod API key is valid: `echo $RUNPOD_API_KEY`
2. Test query manually with RunPod GraphQL explorer
3. Check if API schema changed (rare but possible)
4. Verify internet connectivity

### Issue: Too Many Regions Filtered Out

**Symptom:** Catalog has very few or zero entries

**Solution:**
1. Run with `--no-filter-available` to see full catalog
2. Check if RunPod API is reporting low stock globally
3. Verify `REGION_COUNTRY_CODES` mapping is correct
4. Check logs for API errors

### Issue: Import Errors

**Symptom:** `ModuleNotFoundError` or `ImportError`

**Solution:**
1. Ensure `from functools import lru_cache` is at top of file
2. Check all imports are present
3. Run `python -m py_compile sky/catalog/data_fetchers/fetch_runpod.py`

### Issue: Tests Failing

**Symptom:** Unit tests fail after changes

**Solution:**
1. Check mock setup matches new function signatures
2. Verify test data includes required fields (`stockStatus`)
3. Run tests in isolation: `pytest tests/unit_tests/test_catalog.py -v`

---

## Validation Checklist

Before considering the task complete:

- [ ] Code compiles: `python -m py_compile sky/catalog/data_fetchers/fetch_runpod.py`
- [ ] No linting errors: `make lint`
- [ ] Type checking passes: `make type-check`
- [ ] Unit tests pass: `pytest tests/unit_tests/test_catalog.py`
- [ ] Manual test with filtering enabled works
- [ ] Manual test with filtering disabled works
- [ ] Catalog generation completes without errors
- [ ] `sky show-gpus --cloud runpod` shows only available GPUs
- [ ] Documentation updated in CUSTOM_CHANGES.md
- [ ] Commit message is clear and references this guide
- [ ] PR description explains changes and testing done

---

## Commit Message Template

```
feat(runpod): restore regional availability filtering after v0.11.1 upgrade

Re-add regional availability filtering that was temporarily removed during
the v0.11.1 upgrade when we accepted upstream's major catalog refactor.

Changes:
- Add get_lowest_price_by_region() GraphQL query function
- Add REGION_COUNTRY_CODES mapping for availability checks
- Add filter_available parameter to get_gpu_instance_configurations()
- Add --no-filter-available CLI flag for debugging
- Update documentation and docstrings

The filtering queries RunPod's API for regional stock status and only
includes GPU instances that are actually available for provisioning.
This prevents users from seeing GPUs in the catalog that will fail
to provision due to lack of stock.

Implementation follows fail-open approach: if regional availability
cannot be determined (API errors), the GPU is excluded from that region
but catalog generation continues.

Restored from v0.10.5 implementation, adapted to work with v0.11.1's
new catalog structure (which added CPU support).

Testing:
- Manual testing with RUNPOD_API_KEY
- Verified filtering works with --gpu-ids flag
- Verified --no-filter-available shows full catalog
- Integration test with sky show-gpus --cloud runpod

Fixes: Temporary removal during v0.11.1 upgrade
See: fork/RUNPOD_FILTERING_RESTORATION.md
Related: #9, #21 (original implementation)
```

---

## Time Estimate

- Phase 1 (Understand): 15 minutes
- Phase 2 (Add query): 30 minutes
- Phase 3 (Add filtering): 45 minutes
- Phase 4 (Update main): 15 minutes
- Phase 5 (CLI arg): 10 minutes
- Phase 6 (Documentation): 15 minutes
- Phase 7 (Testing): 1-2 hours
- Phase 8 (Update docs): 15 minutes

**Total:** 3-4 hours

---

## References

- **Old implementation:** `/tmp/our-fetch-runpod.py` (saved during upgrade)
- **Current implementation:** `sky/catalog/data_fetchers/fetch_runpod.py`
- **Original PR:** Check commit `a69bd7c94` and `90d513d4c`
- **Upgrade details:** `fork/UPGRADE_STRATEGY_v0.11.1.md`
- **RunPod API docs:** https://docs.runpod.io/

---

## Contact

For questions or issues:
1. Review this document thoroughly
2. Check `/tmp/our-fetch-runpod.py` for reference implementation
3. Compare with current `sky/catalog/data_fetchers/fetch_runpod.py`
4. Check git history: `git log --all --grep="runpod\|availability" --oneline`

---

**Good luck with the restoration!** 🚀
