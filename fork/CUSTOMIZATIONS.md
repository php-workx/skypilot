# Fork Changes

## Availability-Aware Catalog Fetchers

### Overview
Enhanced catalog fetchers to only include cloud resources that are actually available, preventing SkyPilot from wasting time attempting to provision unavailable GPU instances.

### Implementation Pattern
- Default: Filter to only available resources
- CLI flag: `--no-filter-available` to fall back to all regions/resources


## Custom Catalog URL Support (`feature/custom-catalog-urls` branch)

### Added
- **`sky/catalog/catalog_url_config.py`** - New module for custom catalog URL configuration
  - Support for `SKYPILOT_CATALOG_BASE_URL` (global override)
  - Support for `SKYPILOT_<CLOUD>_CATALOG_URL` (cloud-specific override, e.g., `SKYPILOT_RUNPOD_CATALOG_URL`)

## Development Tooling

### Added
- **`Makefile`** - convenient local development

### Modified
- **`.github/workflows/*.yml`** - Updated Python version checks to 3.11
- **`.github/`** - Moved original GitHub workflows to `_github/` to disable upstream CI
