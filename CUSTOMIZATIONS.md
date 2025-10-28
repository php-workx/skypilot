# Fork Changes

## RunPod Catalog Fetcher

### Added
- **`sky/catalog/data_fetchers/fetch_runpod.py`** - Automated RunPod catalog data fetcher
  - Queries RunPod API for GPU types, pricing, and availability
- **`.github/workflows/build-push-ecr-custom.yaml`** - Custom ECR build/push workflow

### Modified
- **`sky/catalog/runpod_catalog.py`** - Updated to work with fetcher

## Custom Catalog URL Support (`feature/custom-catalog-urls` branch)

### Added
- **`sky/catalog/catalog_url_config.py`** - New module for custom catalog URL configuration
  - Support for `SKYPILOT_CATALOG_BASE_URL` (global override)
  - Support for `SKYPILOT_<CLOUD>_CATALOG_URL` (cloud-specific override, e.g., `SKYPILOT_RUNPOD_CATALOG_URL`)
  - Hardened cloud-name parsing for edge cases

### Modified
- **`sky/catalog/common.py`** - Use `catalog_url_config` module in `_get_catalog_path()`
- **`Dockerfile`** - Make `SKYPILOT_RUNPOD_CATALOG_URL` overridable at build time via ARG

## Development Tooling

### Added
- **`Makefile`** - convenient local development

### Modified
- **`.github/workflows/*.yml`** - Updated Python version checks to 3.11
- **`.github/`** - Moved original GitHub workflows to `_github/` to disable upstream CI
