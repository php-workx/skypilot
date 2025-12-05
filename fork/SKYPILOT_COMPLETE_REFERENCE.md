# SkyPilot Complete Reference: Provisioning, Availability & Blocking

Comprehensive guide to SkyPilot's resource management, pricing updates, availability checking, multi-region failover, and blocking mechanisms

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Pricing Architecture](#pricing-architecture)
3. [Availability Checking](#availability-checking)
4. [RunPod L40S Specifics](#runpod-l40s-specifics)
5. [Multi-Region Failover](#multi-region-failover)
6. [Blocking Granularity](#blocking-granularity)
7. [Cloud-Specific Details](#cloud-specific-details)
8. [Practical Recommendations](#practical-recommendations)
9. [Code Reference](#code-reference)

---

## Executive Summary

### Key Findings

**Pricing Management**:
- ✅ CSV-based catalog stored locally at `~/.sky/catalogs/v8/{cloud}/vms.csv`
- ✅ Auto-updated from GitHub/S3 (GCP/Cudo: 7 hours, others: manual)
- ✅ Changes picked up immediately on next CLI command (new process)

**Availability Checking**:
- ❌ **RunPod**: NO real-time availability check - relies on static catalog
- ✅ **Other clouds**: Real-time API queries during provisioning (varies by cloud)
- ❌ First availability check happens at `create_pod()` call (too late)

**Multi-Region Failover**:
- ✅ **Works with Option 1**: Multiple Resources objects with different regions
- ✅ **Region-specific blocking**: Blocks only failed (cloud, region) pair, not entire cloud
- ❌ **NO automatic multi-region within one Resources object**: Can't specify `region: [CZ, NL, SE]`
- ✅ **Sequential failover**: Tries resources in order, exhausting zones per region before next

**Blocking Behavior**:
- ✅ **Fine-grained**: Blocks based on (cloud, region, instance_type, accelerators)
- ✅ **Conjunctive matching**: ALL specified fields must match to block
- ✅ **Multiple regions of same cloud work**: Each is treated as separate resource

---

## Pricing Architecture

### Overview

SkyPilot uses a **hybrid pricing system**:
- **Pricing data**: Cached locally in CSV files
- **Updates**: Periodic fetch from hosted repository
- **Availability**: Real-time API queries (cloud-dependent)

### Storage Locations

#### Remote (source of truth)

```text
Primary:  https://raw.githubusercontent.com/skypilot-org/skypilot-catalog/master/catalogs/v8/{cloud}/vms.csv
Fallback: https://skypilot-catalog.s3.us-east-1.amazonaws.com/catalogs/v8/{cloud}/vms.csv
```

#### Local cache

```text
~/.sky/catalogs/v8/
├── aws/vms.csv
├── gcp/vms.csv
├── azure/vms.csv
├── runpod/vms.csv
├── cudo/vms.csv
└── ...
```

**Schema version**: `v8` (defined in `sky/skylet/constants.py`)

### Update Mechanism

**File**: `sky/catalog/common.py:read_catalog()`

#### Update frequency by cloud

| Cloud | Update Policy | Reason |
|-------|--------------|--------|
| GCP | Auto-fetch every 7 hours | Prices change frequently |
| Cudo | Auto-fetch every 7 hours | Dynamic component pricing |
| AWS | Manual updates only | Stable pricing, complex fetching |
| Azure | Manual updates only | Stable pricing |
| RunPod | Never auto-update | Static CSV, manual maintenance |

**Update logic**:
```python
def read_catalog(cloud: str):
    catalog_path = get_catalog_path(f"{cloud}/vms.csv")

    # Check if update needed
    if should_update(catalog_path, cloud):
        # Download from GitHub (or S3 fallback)
        download_catalog(catalog_path, cloud)

    # Load into LazyDataFrame
    return LazyDataFrame(catalog_path)
```

**MD5 protection**:
- Calculates MD5 hash of local file
- Compares with downloaded version
- Only overwrites if actually changed
- **Preserves manual edits**: If you edit CSV locally, auto-update skips it

### Runtime CSV Loading

**Key class**: `LazyDataFrame` (`sky/catalog/common.py:124-163`)

```python
class LazyDataFrame:
    """Lazy-loads CSV only when first accessed"""

    def __init__(self, path):
        self._df = None  # Not loaded yet
        self._path = path

    def __call__(self):
        if self._df is None:
            self._df = pd.read_csv(self._path)  # Load on first access
        return self._df
```

**Three-level caching**:

1. **Request-level cache** (via `@lru_cache(scope='request')`):
   - Cleared after each CLI command
   - Implemented in `sky/utils/annotations.py`

2. **Instance-level cache** (`_df` variable):
   - Persists until `LazyDataFrame` instance recreated
   - One per cloud catalog

3. **Module-level cache** (singleton `LazyDataFrame`):
   - Lives for entire Python process
   - Reloaded on each new CLI command (new process)

**Result**: CSV changes are picked up on next `sky` command automatically.

### Manual CSV Editing

**You can edit CSVs freely**:

```bash
# 1. Edit pricing
vim ~/.sky/catalogs/v8/runpod/vms.csv

# 2. Next command picks it up immediately
sky show-gpus --cloud runpod

# 3. Auto-update won't overwrite (MD5 protection)
# Your changes are preserved
```

### Data Fetchers (For Maintainers)

**Location**: `sky/catalog/data_fetchers/`

**Per-cloud fetchers**:
- `fetch_aws.py` - Complex: queries 5 AWS APIs in parallel
- `fetch_gcp.py` - Complex: Compute + SKUs + Accelerators APIs
- `fetch_azure.py` - Medium complexity
- `fetch_cudo.py` - Simple: component-based pricing
- `fetch_runpod.py` - Simple: manual CSV generation

**Usage** (to update pricing):
```bash
cd sky/catalog/data_fetchers
python fetch_runpod.py > ../../catalogs/v8/runpod/vms.csv
```

---

## Availability Checking

### The Critical Distinction

**Pricing vs Availability**:
- **Pricing**: Stored in CSV (static)
- **Availability**: Cloud-dependent (varies by provider)

### RunPod: NO Real-Time Availability Check

**File**: `sky/clouds/runpod.py:regions_with_offering()`

```python
@classmethod
def regions_with_offering(cls, instance_type, accelerators, ...):
    # Query CATALOG, not RunPod API
    regions = catalog.get_region_zones_for_instance_type(
        instance_type, use_spot, 'runpod'
    )
    return regions  # ← Returns regions from CSV
```

**No API call to check current inventory**. The catalog says:
- "L40S exists in CZ region" ✓
- NOT "L40S currently has 5 units available in CZ" ✗

**First real availability check**:

**File**: `sky/provision/runpod/instance.py:98-125`

```python
def run_instances(...):
    for _ in range(to_start_count):
        try:
            # First time we know availability is HERE
            instance_id = utils.launch(...)  # ← Calls create_pod()
        except Exception as e:
            # Too late - already failed
            raise
```

#### What happens

```text
1. User: sky launch --gpus L40S --region CZ
   ↓
2. SkyPilot checks catalog: "CZ has L40S: ✓"
   ↓
3. SkyPilot calls: runpod.create_pod(gpu_type='NVIDIA L40S', region='CZ')
   ↓
4. RunPod API: "Error: No L40S inventory in CZ"
   ↓
5. SkyPilot: FAILS (no fallback within this region attempt)
```

### Other Clouds: Varies

**Cudo**: Real-time availability check

**File**: `sky/provision/cudo/cudo_wrapper.py:vm_available()`

```python
def vm_available(instance_type, region):
    # Query API for CURRENT availability
    response = api.list_vm_machine_types2(...)

    # Calculate max instances possible
    available_instances = min(
        available_vcpu // required_vcpu,
        available_memory // required_memory,
        available_gpu // required_gpu
    )
    return available_instances > 0
```

**AWS/GCP/Azure**: Real-time during provisioning, varies by implementation

### The Gap: No Pre-Flight Check for RunPod

**What's missing**:
```python
# This doesn't exist for RunPod:
def check_availability_before_launch(gpu_type, region):
    response = runpod_api.get_availability(
        gpu_type=gpu_type,
        region=region
    )
    return response['available_count'] > 0

# Would allow:
if check_availability_before_launch('L40S', 'CZ'):
    launch(...)
else:
    try_next_region()
```

**Why it doesn't exist**:
- RunPod API may not expose `/availability` endpoint
- Static catalog assumed sufficient
- Real-time checks would add latency

---

## RunPod L40S Specifics

### European Regions with L40S

**From catalog** (`~/.sky/catalogs/v8/runpod/vms.csv`):

| Region Code | Country | Zones |
|-------------|---------|-------|
| **IS** | Iceland | EUR-IS-1, EUR-IS-2, EUR-IS-3 |
| **CZ** | Czech Republic | EU-CZ-1 |
| **NL** | Netherlands | EU-NL-1 |
| **SE** | Sweden | EU-SE-1 |
| **RO** | Romania | EU-RO-1 |
| **NO** | Norway | EU-SE-1 |

**Total**: 6 countries, ~9 zones

**Best odds**: Iceland (IS) - 3 zones vs 1 zone in other regions

### GPU ID Mapping

**File**: `sky/provision/runpod/utils.py:16-74`

```python
GPU_NAME_MAP = {
    'L40S': 'NVIDIA L40S',  # ← SkyPilot → RunPod mapping
    'L40': 'NVIDIA L40',
    'A100': 'NVIDIA A100-PCIE-40GB',
    # ...
}

# Usage in launch:
gpu_type = GPU_NAME_MAP[accelerator_name]
runpod.create_pod(gpu_type_id=gpu_type, ...)
```

**Important**: Hardcoded mapping. If RunPod changes GPU ID format, SkyPilot breaks.

### Why L40S Fails Frequently in EU

**Root causes**:

1. **High demand**: L40S is popular (good performance/price)
2. **Limited EU inventory**: Fewer datacenters than US
3. **Static catalog**: Shows "available" even when inventory is zero
4. **No pre-check**: Only discovers unavailability when `create_pod()` fails
5. **Sequential retry**: By the time next region is tried, it may also be empty

**Catalog vs Reality**:
- **Catalog**: "L40S available in 6 EU regions" ✓
- **Reality**: "L40S currently in stock: 0 regions" (at that moment)

### The Launch Sequence

```text
User specifies: L40S in EU region
  ↓
Optimizer selects: (RunPod, IS, L40S:1)  [Iceland - best odds]
  ↓
_retry_zones() tries:
  - EUR-IS-1: create_pod() → "No inventory"
  - EUR-IS-2: create_pod() → "No inventory"
  - EUR-IS-3: create_pod() → "No inventory"
  ↓
All zones fail → blocks (RunPod, IS) → returns to optimizer
  ↓
Optimizer selects: (RunPod, CZ, L40S:1)  [Czech Republic]
  ↓
_retry_zones() tries:
  - EU-CZ-1: create_pod() → "No inventory"
  ↓
Blocks (RunPod, CZ) → optimizer tries next...
  ↓
Continues through NL, SE, RO, NO...
  ↓
If all fail: ResourcesUnavailableError
```

### Workarounds

**1. Check RunPod console first**:
```bash
# Before SkyPilot launch:
# 1. Go to runpod.io console
# 2. Check GPU availability manually
# 3. Note which regions have L40S
# 4. Launch SkyPilot targeting that region
```

**2. Use multi-region auto-failover** (you already do this):
```yaml
resources:
  - cloud: runpod
    region: IS  # Iceland (3 zones)
  - cloud: runpod
    region: NL  # Netherlands
  - cloud: runpod
    region: CZ  # Czech Republic
  # ... all EU regions
```

**3. Add other clouds as fallback**:
```yaml
resources:
  - cloud: runpod
    region: IS
    accelerators: L40S:1
  - cloud: vast
    region: eu-se-1
    accelerators: L40S:1
  - cloud: lambda
    region: europe-central-1
    accelerators: A100:1  # Alternative GPU
```

**4. Retry script**:
```bash
#!/bin/bash
REGIONS=("IS" "NL" "CZ" "SE" "RO" "NO")
for region in "${REGIONS[@]}"; do
    echo "Trying region: $region"
    if sky launch -y -n test --gpus L40S --region "$region"; then
        echo "Success in $region!"
        exit 0
    fi
done
echo "No L40S available in any EU region"
exit 1
```

---

## Multi-Region Failover

### The Design Limitation

**SkyPilot supports**:
- ✅ Multi-zone failover (within one region)
- ✅ Multi-cloud failover (across different clouds)
- ❌ Multi-region failover (within same cloud via single Resources object)

**What this means**:

**Does NOT work**:
```yaml
resources:
  cloud: runpod
  region: [CZ, NL, SE]  # ← Can't specify array of regions
  accelerators: L40S:1
```

**DOES work** (Option 1 - auto-failover):
```yaml
resources:
  - cloud: runpod
    region: CZ
    accelerators: L40S:1
  - cloud: runpod
    region: NL
    accelerators: L40S:1
  - cloud: runpod
    region: SE
    accelerators: L40S:1
```

### How Auto-Failover Works

**Documentation**: [SkyPilot Auto-Failover Guide](https://docs.skypilot.co/en/latest/examples/auto-failover.html)

**Failover sequence**:

1. **Regional failover first**: Try all zones within chosen region
2. **Cross-resource failover second**: If all zones fail, try next Resources object
3. **Cross-cloud failover**: If all resources fail, try different cloud

**Code flow**:

**File**: `sky/backends/cloud_vm_ray_backend.py:2202-2387`

```python
def provision_with_retries(self, task, to_provision_config, ...):
    """Try provisioning with auto-failover"""

    while True:  # Outer loop: tries different Resources objects
        try:
            # Inner loop: tries zones within one region
            config_dict = self._retry_zones(
                to_provision=task.best_resources,
                num_nodes=to_provision_config.num_nodes,
                ...
            )
            break  # Success!

        except exceptions.ResourcesUnavailableError as e:
            # Zone retry failed → block this resource
            self._add_to_blocked_resources(
                self._blocked_resources,
                task.best_resources  # ← Blocks (cloud, region, instance, accel)
            )

            # Re-optimize to pick next Resources object
            task.best_resources = None
            self._dag = optimizer.Optimizer.optimize(
                self._dag,
                minimize=self._optimize_target,
                blocked_resources=self._blocked_resources
            )
```

**Zone retry loop**:

**File**: `sky/backends/cloud_vm_ray_backend.py:1497-1820`

```python
def _retry_zones(self, to_provision, num_nodes, ...):
    """Try all zones within the selected region"""

    # Region is FIXED (set by optimizer)
    assert to_provision.region is not None
    region = clouds.Region(to_provision.region)

    # Try each zone in this region
    for zones in self._yield_zones(to_provision, num_nodes, ...):
        try:
            provision_record = provisioner.bulk_provision(
                cloud=to_provision.cloud,
                region=region,
                zones=zones,  # ← One zone at a time
                ...
            )
            return provision_record  # Success!
        except Exception as e:
            continue  # Try next zone

    # All zones failed
    raise exceptions.ResourcesUnavailableError(...)
```

**Key insight**: The inner loop (`_retry_zones`) only tries zones within ONE region. The outer loop (`provision_with_retries`) tries different Resources objects.

### Example Execution Flow

**Config**:
```yaml
resources:
  - cloud: runpod
    region: IS
    accelerators: L40S:1
  - cloud: runpod
    region: CZ
    accelerators: L40S:1
  - cloud: runpod
    region: NL
    accelerators: L40S:1
```

#### Execution

```text
Optimizer picks: (RunPod, IS, L40S:1)
  ↓
_retry_zones() tries all zones in IS:
  EUR-IS-1: create_pod() → FAIL (no inventory)
  EUR-IS-2: create_pod() → FAIL
  EUR-IS-3: create_pod() → FAIL
  ↓
All zones failed → ResourcesUnavailableError
  ↓
Block (RunPod, IS, instance, L40S) ← Region-specific!
  ↓
Optimizer picks: (RunPod, CZ, L40S:1)
  ↓
_retry_zones() tries all zones in CZ:
  EU-CZ-1: create_pod() → FAIL (no inventory)
  ↓
Block (RunPod, CZ, instance, L40S)
  ↓
Optimizer picks: (RunPod, NL, L40S:1)
  ↓
_retry_zones() tries all zones in NL:
  EU-NL-1: create_pod() → SUCCESS! ✓
  ↓
Return instance_id
```

**Result**: All regions get tried sequentially, exhausting zones in each before moving to next.

---

## Blocking Granularity

### The Question

When using auto-failover with multiple Resources objects:
```yaml
resources:
  - cloud: runpod, region: IS
  - cloud: runpod, region: CZ
  - cloud: runpod, region: NL
```

**When IS fails, what gets blocked?**
- Entire RunPod cloud? (blocks CZ and NL too)
- Just that Resources object? (CZ and NL still tried)

### The Answer: Region-Specific Blocking ✅

**Only the specific (cloud, region, instance, accelerators) combination gets blocked.**

**File**: `sky/resources.py:1752-1775`

```python
def should_be_blocked_by(candidate: Resources,
                        blocked: Resources) -> bool:
    """
    Conjunctive matching: ALL non-None fields must match to block.

    Returns True if candidate should be blocked by blocked resource.
    """

    # Check cloud
    if blocked.cloud is not None and candidate.cloud != blocked.cloud:
        return False  # Different cloud → NOT blocked

    # Check region ← KEY CHECK
    if blocked.region is not None and candidate.region != blocked.region:
        return False  # Different region → NOT blocked

    # Check instance type
    if blocked.instance_type is not None and \
       candidate.instance_type != blocked.instance_type:
        return False

    # Check accelerators
    if blocked.accelerators is not None and \
       candidate.accelerators != blocked.accelerators:
        return False

    # All specified fields match → BLOCKED
    return True
```

**Blocking logic**: Conjunctive (AND), not disjunctive (OR)

### Example Blocking Scenarios

#### Scenario 1: Different regions, same cloud

```python
blocked = Resources(cloud='runpod', region='IS', instance='gpu', accel={'L40S': 1})
candidate = Resources(cloud='runpod', region='CZ', instance='gpu', accel={'L40S': 1})

# Check: blocked.region ('IS') != candidate.region ('CZ')
# Result: NOT BLOCKED ✓
```

#### Scenario 2: Same region

```python
blocked = Resources(cloud='runpod', region='IS', instance='gpu', accel={'L40S': 1})
candidate = Resources(cloud='runpod', region='IS', instance='gpu', accel={'L40S': 1})

# Check: All fields match
# Result: BLOCKED ✓
```

#### Scenario 3: Different GPU, same region

```python
blocked = Resources(cloud='runpod', region='IS', instance='gpu', accel={'L40S': 1})
candidate = Resources(cloud='runpod', region='IS', instance='gpu', accel={'A100': 1})

# Check: blocked.accel ({'L40S':1}) != candidate.accel ({'A100':1})
# Result: NOT BLOCKED ✓
```

#### Scenario 4: Different cloud

```python
blocked = Resources(cloud='runpod', region='IS', instance='gpu', accel={'L40S': 1})
candidate = Resources(cloud='vast', region='IS', instance='gpu', accel={'L40S': 1})

# Check: blocked.cloud ('runpod') != candidate.cloud ('vast')
# Result: NOT BLOCKED ✓
```

### Blocking Granularity Summary

| Blocked Resource | Candidate Resource | Blocked? | Reason |
|-----------------|-------------------|----------|--------|
| (RunPod, IS, L40S) | (RunPod, IS, L40S) | ✅ Yes | Exact match |
| (RunPod, IS, L40S) | (RunPod, CZ, L40S) | ❌ No | Different region |
| (RunPod, IS, L40S) | (RunPod, IS, A100) | ❌ No | Different GPU |
| (RunPod, IS, L40S) | (Vast, IS, L40S) | ❌ No | Different cloud |
| (RunPod, None, L40S) | (RunPod, CZ, L40S) | ✅ Yes | None = wildcard |

**Key takeaway**: Blocking is **fine-grained**, not cloud-wide.

### How Blocking Is Added

**File**: `sky/backends/cloud_vm_ray_backend.py:2323`

```python
def _add_to_blocked_resources(blocked_resources, to_provision):
    """Add the specific resource configuration to blocked set"""
    blocked_resources.add(to_provision)  # ← Entire Resources object
```

**What gets added**: The full `Resources` object with all fields:
- cloud='runpod'
- region='IS'
- instance_type='gpu'
- accelerators={'L40S': 1}

**Not just the cloud name**, not just (cloud, region), but the entire configuration.

### How Optimizer Filters Blocked Resources

**File**: `sky/optimizer.py:1183-1192`

```python
def _filter_out_blocked_resources(resources_list, blocked_resources):
    """Remove blocked resources from candidate list"""

    filtered = []
    for resources in resources_list:
        # Check if this resource is blocked
        is_blocked = any(
            resources.should_be_blocked_by(blocked)
            for blocked in blocked_resources
        )
        if not is_blocked:
            filtered.append(resources)

    return filtered
```

**The check**: Calls `should_be_blocked_by()` for each blocked resource.

**Result**: Only resources that match ALL non-None fields of a blocked resource are filtered out.

### Practical Implications

**Your auto-failover config works correctly!**

```yaml
resources:
  - cloud: runpod
    region: IS
  - cloud: runpod
    region: CZ
  - cloud: runpod
    region: NL
```

#### Execution

```text
Try (RunPod, IS) → All zones fail
  ↓
Block: (RunPod, IS, instance, L40S)
  ↓
Check (RunPod, CZ): region differs → NOT blocked → TRY ✓
  ↓
Try (RunPod, CZ) → Fail
  ↓
Block: (RunPod, CZ, instance, L40S)
  ↓
Check (RunPod, NL): region differs → NOT blocked → TRY ✓
```

**All your regions get tried** because each has a different region field.

---

## Cloud-Specific Details

### RunPod

**Catalog location**: `~/.sky/catalogs/v8/runpod/vms.csv`

**Update frequency**: Never (static, manually maintained)

**Availability check**: None (relies on catalog)

**Region format**: ISO country codes (CZ, NL, SE, etc.)

**Zone format**: `{CONTINENT}-{COUNTRY}-{NUMBER}` (e.g., EU-CZ-1)

**GPU mapping**: Hardcoded in `sky/provision/runpod/utils.py:GPU_NAME_MAP`

**Key limitation**: No real-time inventory visibility

**Provisioning files**:
- `sky/clouds/runpod.py` - Cloud interface
- `sky/provision/runpod/instance.py` - Provisioning logic
- `sky/provision/runpod/utils.py` - Launch helpers, GPU mapping
- `sky/catalog/runpod_catalog.py` - Catalog loading

### Cudo

**Catalog location**: `~/.sky/catalogs/v8/cudo/vms.csv`

**Update frequency**: Auto-fetch every 7 hours

**Availability check**: Real-time via `list_vm_machine_types2()` API

**Pricing model**: Component-based (CPU + RAM + GPU)

**Key strength**: Real-time availability prevents wasted launch attempts

**Provisioning files**:
- `sky/clouds/cudo.py`
- `sky/provision/cudo/instance.py`
- `sky/provision/cudo/cudo_wrapper.py` - Availability checking

### GCP

**Catalog location**: `~/.sky/catalogs/v8/gcp/vms.csv`

**Update frequency**: Auto-fetch every 7 hours

**Availability check**: Real-time during provisioning

**Complexity**: Multiple CSVs (vms, images, accelerator_quota_mapping)

**Key feature**: Extensive regional coverage

### AWS

**Catalog location**: `~/.sky/catalogs/v8/aws/vms.csv`

**Update frequency**: Manual (stable pricing)

**Availability check**: Real-time during provisioning

**Complexity**: High (queries 5 APIs in parallel)

**Key feature**: Most comprehensive region/zone coverage

---

## Practical Recommendations

### For RunPod L40S in Europe

**1. Optimize region order** - Iceland first (3 zones):
```yaml
resources:
  - cloud: runpod
    region: IS  # Iceland - best odds
  - cloud: runpod
    region: NL  # Netherlands
  - cloud: runpod
    region: CZ  # Czech Republic
  - cloud: runpod
    region: SE  # Sweden
  - cloud: runpod
    region: RO  # Romania
  - cloud: runpod
    region: NO  # Norway
```

**2. Add multi-cloud fallback**:
```yaml
resources:
  - cloud: runpod
    region: IS
    accelerators: L40S:1
  - cloud: vast
    region: eu-se-1
    accelerators: L40S:1
  - cloud: lambda
    region: europe-central-1
    accelerators: L40S:1
```

**3. Include alternative GPUs**:
```yaml
resources:
  any_of:
    - cloud: runpod
      region: IS
      accelerators: L40S:1
    - cloud: runpod
      region: IS
      accelerators: A40:1  # Similar performance
    - cloud: runpod
      region: IS
      accelerators: A100:1  # Higher performance
```

**4. Check availability before launch**:
```bash
# Manual check via RunPod console
# OR create monitoring script:

#!/bin/bash
# check_runpod_availability.sh

REGIONS=("IS" "NL" "CZ" "SE")
for region in "${REGIONS[@]}"; do
    echo "Checking $region..."
    # Would need RunPod API integration
    # Not currently exposed in SkyPilot
done
```

**5. Use retry wrapper script**:
```bash
#!/bin/bash
# retry_launch.sh

MAX_RETRIES=3
RETRY_DELAY=60  # seconds

for i in $(seq 1 $MAX_RETRIES); do
    echo "Launch attempt $i of $MAX_RETRIES"

    if sky serve up -n my-service service.yaml; then
        echo "Success!"
        exit 0
    fi

    if [ $i -lt $MAX_RETRIES ]; then
        echo "Failed. Waiting ${RETRY_DELAY}s before retry..."
        sleep $RETRY_DELAY
    fi
done

echo "All retries failed"
exit 1
```

### General Best Practices

**1. Always use auto-failover** for production:
```yaml
resources:
  - cloud: primary_choice
    region: preferred_region
  - cloud: backup_choice
    region: backup_region
```

**2. Monitor catalog freshness**:
```bash
stat ~/.sky/catalogs/v8/runpod/vms.csv
# If >24 hours old, consider refreshing:
rm ~/.sky/catalogs/v8/runpod/vms.csv
sky show-gpus --cloud runpod  # Triggers re-download
```

**3. Keep local overrides separate**:
```bash
# Don't edit main catalog - create override:
cp ~/.sky/catalogs/v8/runpod/vms.csv ~/.sky/catalogs/v8/runpod/vms_custom.csv
# Edit vms_custom.csv
# Point your config to custom catalog
```

**4. Test failover logic**:
```bash
# Intentionally block regions to test failover:
sky launch test.yaml --region INVALID_REGION
# Should fail and try next region
```

**5. Log provisioning attempts**:
```bash
sky serve up -n test service.yaml 2>&1 | tee provision.log
# Review which regions were tried
grep "Launching" provision.log
```

---

## Code Reference

### Key Files

**Optimizer**:
- `sky/optimizer.py:109-142` - Resource selection
- `sky/optimizer.py:1183-1192` - Blocked resource filtering

**Provisioning orchestration**:
- `sky/backends/cloud_vm_ray_backend.py:2202-2387` - `provision_with_retries()`
- `sky/backends/cloud_vm_ray_backend.py:1497-1820` - `_retry_zones()`
- `sky/backends/cloud_vm_ray_backend.py:2323` - `_add_to_blocked_resources()`

**Blocking logic**:
- `sky/resources.py:1752-1775` - `should_be_blocked_by()`

**Catalog management**:
- `sky/catalog/common.py:69-82` - MD5 checking
- `sky/catalog/common.py:124-163` - `LazyDataFrame` class
- `sky/catalog/common.py:165-254` - `read_catalog()`

**RunPod-specific**:
- `sky/clouds/runpod.py:102-120` - `zones_provision_loop()`
- `sky/provision/runpod/instance.py:98-125` - `run_instances()`
- `sky/provision/runpod/utils.py:16-74` - `GPU_NAME_MAP`
- `sky/provision/runpod/utils.py:launch()` - Create pod logic

**Cudo-specific**:
- `sky/provision/cudo/cudo_wrapper.py:vm_available()` - Real-time check

**Cache management**:
- `sky/utils/annotations.py:32-62` - Request-scoped cache decorator

### Key Constants

**File**: `sky/skylet/constants.py`

```python
CATALOG_SCHEMA_VERSION = 'v8'
CATALOG_DIR = '~/.sky/catalogs/{CATALOG_SCHEMA_VERSION}/'
HOSTED_CATALOG_DIR_URL = 'https://raw.githubusercontent.com/skypilot-org/skypilot-catalog/master/catalogs'
HOSTED_CATALOG_DIR_URL_S3_MIRROR = 'https://skypilot-catalog.s3.us-east-1.amazonaws.com/catalogs'
```

### Key Data Structures

**Resources object**:
```python
class Resources:
    cloud: str  # 'runpod', 'gcp', 'aws', etc.
    region: str  # 'IS', 'us-east-1', etc.
    zone: str  # 'EUR-IS-1', 'us-east-1a', etc.
    instance_type: str  # 'gpu', 'n1-standard-4', etc.
    accelerators: Dict[str, int]  # {'L40S': 1}
    # ... other fields
```

**Catalog CSV columns**:
```csv
InstanceType,AcceleratorName,AcceleratorCount,vCPUs,MemoryGiB,GpuInfo,Region,SpotPrice,Price,AvailabilityZone
```

### Debug Commands

**Check catalog contents**:
```bash
cat ~/.sky/catalogs/v8/runpod/vms.csv | grep L40S
```

**Check catalog age**:
```bash
stat -f "%Sm" ~/.sky/catalogs/v8/runpod/vms.csv
```

**Force catalog refresh**:
```bash
rm ~/.sky/catalogs/v8/runpod/vms.csv
sky show-gpus --cloud runpod
```

**View optimizer decisions** (enable debug logging):
```bash
export SKYPILOT_DEBUG=1
sky launch test.yaml
```

**Check blocked resources** (in Python debugger):
```python
# Set breakpoint in sky/backends/cloud_vm_ray_backend.py
print(self._blocked_resources)
```

---

## Conclusion

### Summary of Key Insights

**Pricing**:
- CSV-based, locally cached, auto-updated (frequency varies by cloud)
- Changes picked up immediately on next CLI command
- MD5 protection preserves manual edits

**Availability**:
- RunPod: No real-time check, relies on static catalog
- Other clouds: Real-time API queries (varies by provider)
- First availability check happens at `create_pod()` call (too late for pre-filtering)

**Multi-Region Failover**:
- Works via auto-failover (Option 1): multiple Resources objects
- Sequential: tries all zones in one region before moving to next
- Region-specific blocking: doesn't block entire cloud

**Blocking**:
- Fine-grained: (cloud, region, instance, accelerators)
- Conjunctive matching: ALL fields must match to block
- Multiple regions of same cloud work correctly

**RunPod L40S EU Challenge**:
- No pre-check + high demand + limited inventory = frequent failures
- Auto-failover helps but all regions may genuinely be empty
- Solution: multi-cloud fallback + alternative GPUs + manual monitoring

### Next Steps

**If experiencing L40S unavailability**:
1. Verify auto-failover config includes all EU regions
2. Add other clouds (Vast, Lambda) as fallback
3. Include alternative GPUs (A40, A100)
4. Check RunPod console before launching
5. Consider retry wrapper script

**If contributing to SkyPilot**:
1. Add pre-provisioning availability check for RunPod
2. Expose availability API endpoint (if RunPod supports)
3. Improve error messages to distinguish "no inventory" vs "provisioning failed"
4. Add availability forecasting based on historical data

**If debugging provisioning issues**:
1. Check catalog age and contents
2. Enable debug logging (`SKYPILOT_DEBUG=1`)
3. Review provision logs for region attempt sequence
4. Verify blocking behavior with multiple Resources objects

---

**Document compiled from**:
- `skypilot_pricing_architecture.md`
- `skypilot_cloud_specifics.md`
- `runpod_l40s_availability_analysis.md`
- `skypilot_multiregion_analysis.md`
- `BLOCKING_GRANULARITY_EXECUTIVE_SUMMARY.md`
- `blocking_granularity_analysis.md`

**All source code references verified against**: `/Users/runger/workspaces/amplifier/ai_working/skypilot/`

---

---

<!-- End of Complete Reference -->
