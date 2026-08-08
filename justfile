# Sync the dev environment and install the coverage subprocess startup hook.
# The hook is the canonical mechanism (per coverage.py docs) for measuring
# import-time code that pytest-cov would otherwise miss because the package is
# imported during pytest plugin discovery, before instrumentation starts.
# Idempotent: rewrites the .pth file each run because `uv sync --frozen` may
# rebuild the venv from scratch.
setup:
    uv sync --frozen --all-extras --group dev --group docs
    @uv run --no-sync python scripts/install_coverage_hook.py

# Run the full pytest suite under coverage.
# COVERAGE_PROCESS_START activates the coverage_subprocess.pth hook (installed
# by `just setup`), which starts coverage at Python interpreter startup so
# import-time class/function definitions are measured even when pytest-cov
# imports `card_bin_data` early during plugin discovery.
test:
    COVERAGE_PROCESS_START=pyproject.toml uv run --no-sync pytest -n 0 --cov=card_bin_data --cov-branch --cov-report=term-missing --cov-fail-under=100

# Lint the codebase and apply safe Ruff fixes.
lint:
    uv run --no-sync ruff check --fix .

# Format the codebase with Ruff.
format:
    uv run --no-sync ruff format --preview .

# Check formatting without changing files.
format-check:
    uv run --no-sync ruff format --preview --check .

# Run static type checks with ty.
typecheck:
    uv run --no-sync ty check

# Validate immutable GitHub Action and Docker image references.
pin-check:
    uv run --no-sync python scripts/validate_dependency_pins.py

# Validate declared runtime dependencies.
deptry-check:
    uv run --no-sync deptry .

# Audit dependencies for known vulnerabilities and dependency issues.
audit:
    uv run --no-sync python scripts/audit_dependencies.py
    uv run --no-sync deptry .

# Build source and wheel distributions.
build:
    uv run --no-sync python scripts/release_artifacts.py build --dist-dir dist

# Serve documentation locally (Zensical, config in zensical.toml).
docs-serve:
    uv run --frozen --group docs zensical serve

# Build static documentation site.
docs-build:
    uv run --frozen --group docs zensical build --clean

# Run all configured prek hooks.
prek:
    uv run --no-sync prek run --show-diff-on-failure --color=always --all-files

# Run CI-style checks without auto-fixing files.
check:
    uv run --no-sync ruff check .
    uv run --no-sync ruff format --preview --check .
    uv run --no-sync ty check
    uv run --no-sync python scripts/validate_dependency_pins.py

# Alias for the dependency audit command.
security: audit
