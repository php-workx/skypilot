# SkyPilot Development Guidelines for AI Assistants

This file provides guidance for AI assistants working with the SkyPilot codebase.

## Python Version

**CRITICAL**: This project uses **Python 3.10** in production.

- Always use Python 3.10 for development and testing
- Virtual environment setup: `uv venv --python 3.10 .venv`
- All code must be compatible with Python 3.10+

## Development Environment

### DevContainer (Recommended)

The `ojin-release` branch has a proper DevContainer configuration at `.devcontainer/devcontainer.json`:

**Features:**
- Based on `continuumio/miniconda3:23.5.2-0` (includes Python via conda)
- Uses `Dockerfile_debug` for the container build
- Pre-configured environment variables:
  - `SKYPILOT_DEBUG=1`
  - `SKYPILOT_DEV=1`
  - `SKYPILOT_DISABLE_USAGE_COLLECTION=1`
- `uv` package manager pre-installed
- VSCode extensions: Python, Black formatter, isort, Ruff
- Python interpreter: `/opt/conda/bin/python`
- Mounts for `.sky`, `.config`, `.ssh`, `.aws`, `.kube`

**Important**: Verify Python version inside the DevContainer and ensure Python 3.10 compatibility:

```bash
python --version  # Should be 3.10.x for SkyPilot production compatibility
```

If the container uses a different Python version, create a Python 3.10 environment:

```bash
conda create -n py310 python=3.10
conda activate py310
```

### Local Development Environment Setup

If not using DevContainer or need Python 3.10 specifically:

#### 1. Create Virtual Environment

```bash
cd /workspace/skypilot
uv venv --python 3.10 .venv
```

### 2. Install Dependencies

```bash
# Install test dependencies
uv pip install -r requirements-dev.txt --python .venv/bin/python

# Install additional required packages
uv pip install pytest runpod cachetools aiofiles \
  sqlalchemy networkx pendulum prettytable tabulate \
  pulp setproctitle gitpython pyjwt alembic aiosqlite \
  casbin sqlalchemy_adapter prometheus_client \
  --python .venv/bin/python
```

## Required Environment Variables

The following environment variables MUST be set when running tests:

```bash
export SKYPILOT_DEBUG=1
export SKYPILOT_DISABLE_USAGE_COLLECTION=1
export PYTHONPATH=/workspace/skypilot
```

These are also configured in `pyproject.toml` for pytest.

## Running Tests

### Run Specific Test Class

```bash
cd /workspace/skypilot
export PYTHONPATH=/workspace/skypilot
export SKYPILOT_DEBUG=1
export SKYPILOT_DISABLE_USAGE_COLLECTION=1

.venv/bin/python -m pytest tests/unit_tests/test_sky/clouds/test_runpod_cloud.py::TestClassName -v
```

### Run All RunPod Tests

```bash
.venv/bin/python -m pytest tests/unit_tests/test_sky/clouds/test_runpod_cloud.py -v
```

Expected result: **All 36 tests should pass**

## Code Quality Standards

### Makefile Commands

The project includes a comprehensive Makefile for common tasks:

```bash
# Setup and Installation
make install          # Install all dependencies with uv (Python 3.10)
make clean           # Remove virtual environment and cache files

# Testing
make test            # Run all local tests (alias for test-local)
make test-unit       # Run unit tests only (fastest)
make test-local      # Run all tests that don't require cloud credentials

# Code Quality
make format          # Format code with yapf, black, and isort
make lint            # Run pylint linting
make type-check      # Run mypy type checking
make check           # Run all code quality checks (format + lint + type-check)

# Development Workflow
make quick           # Quick cycle: format + test-unit
make full            # Full cycle: check + test-local
make pre-commit      # Pre-commit checks: check + test-unit
```

### Before Submitting Changes

Run the quality checks:

```bash
make check    # Runs format, lint, and type-check
make test     # Ensures all tests pass
```

Or use the combined pre-commit check:

```bash
make pre-commit    # Runs all checks + unit tests
```

### Testing Checklist

- [ ] All unit tests pass (`make test-unit` or `make test`)
- [ ] No new test failures introduced
- [ ] Code formatted (`make format`)
- [ ] Linting passes (`make lint` - score should be >9.5/10)
- [ ] Type checking passes (`make type-check`)
- [ ] Code works with Python 3.10
- [ ] Environment variables set correctly
- [ ] No import errors

## Key Files Modified

### Core Implementation
- `sky/clouds/runpod.py` - Main RunPod cloud implementation
  - Added GPU ID mapping using existing `GPU_NAME_MAP`
  - Implemented availability checking with caching
  - Fixed `regions_with_offering()` to handle accelerators

### Tests
- `tests/unit_tests/test_sky/clouds/test_runpod_cloud.py`
  - Added GPU ID mapping tests
  - All 36 tests passing

### Dependencies
- Uses existing `sky/provision/runpod/utils.py` for `GPU_NAME_MAP`
- Imports `runpod` SDK for API calls

## Common Issues and Solutions

### Import Errors

If you see `ModuleNotFoundError`, ensure all dependencies are installed:

```bash
uv pip install <missing-package> --python .venv/bin/python
```

### Test Failures

If tests fail:
1. Check environment variables are set
2. Verify Python 3.10 is being used: `.venv/bin/python --version`
3. Ensure PYTHONPATH is set correctly
4. Check that dependencies are installed in the venv

### Linting/Formatting

Follow existing code style:
- Line length: Reasonable (no strict limit shown in codebase)
- Import organization: Standard lib, third-party, local
- Type hints: Use consistently
- Docstrings: Include for public methods

## Important Notes

1. **Never modify test code** - Only fix implementation to make tests pass
2. **Maintain backward compatibility** - All existing functionality must continue to work
3. **Use fail-open philosophy** - Availability checks should not block provisioning on errors
4. **Reuse existing code** - Don't duplicate functionality (e.g., GPU_NAME_MAP)

## Contact

For questions about this codebase, refer to the main SkyPilot documentation or the project's GitHub repository.
