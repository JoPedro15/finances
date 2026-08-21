# Use python3 as the default interpreter
PYTHON = python3

# Define the source files to be checked
SOURCES = main.py src/
TESTS_DIR = tests/
ALL_SOURCES = $(SOURCES) $(TESTS_DIR)

.PHONY: help install format lint security-check test quality clean sync-portfolio push-config pull-config get-snapshot save-snapshot analyze etf-details stock-details analyze-exposure migrate decision sync-fundamentals

# ==============================================================================
# 📖 Help
# ==============================================================================
# Displays the list of available CLI make commands and descriptions.
help:
	@echo "Available commands:"
	@echo "  --- Setup, Maintenance & Quality ---"
	@echo "  make install          - Installs project and dev dependencies."
	@echo "  make format           - Formats code automatically (black) and fixes lint issues (ruff)."
	@echo "  make lint             - Runs formatter check (black), linter (ruff) and type checker (mypy)."
	@echo "  make security-check   - Runs security analysis (bandit & pip-audit)."
	@echo "  make test             - Runs unit tests (pytest)."
	@echo "  make quality          - Runs full quality gate (lint + security-check + test)."
	@echo "  make clean            - Cleans Python temporary cache files and coverage reports."
	@echo "  --- Project Utils & Decision Engine ---"
	@echo "  make sync-portfolio   - Migrates JSON portfolio to SQLite DB and pushes config to Google Drive."
	@echo "  make push-config      - Pushes local config files to Google Drive."
	@echo "  make pull-config      - Pulls config files from Google Drive."
	@echo "  make migrate          - Migrates existing JSON data to SQLite database."
	@echo "  make get-snapshot     - Displays the current portfolio value."
	@echo "  make save-snapshot    - Saves the current portfolio value to history."
	@echo "  make analyze          - Analyzes overall portfolio performance."
	@echo "  make etf-details ISIN= - Inspects composition and details for an ETF ISIN."
	@echo "  make stock-details TICKER= - Inspects fundamental metrics for a stock ticker or ISIN."
	@echo "  make analyze-exposure - Analyzes portfolio sector and country exposure."
	@echo "  make sync-fundamentals - Synchronizes stock and ETF fundamental metrics into SQLite database."
	@echo "  make decision [FLAGS=...] - Ranks investment targets using live market data."
	@echo "       Available Flags:"
	@echo "         -t, --targets-file PATH : Path to targets wishlist JSON (default: data/portfolio_targets.json)"
	@echo "         -p, --portfolio-file PATH: Path to active holdings JSON (default: data/portfolio.json)"
	@echo "         --skip-ai               : Run quantitative scoring matrix only (bypasses Gemini AI)"
	@echo "         --notify                : Dispatch rebalancing report and chart to Discord webhook"
	@echo "         -v, --verbose           : Display granular factor score breakdowns in table"
	@echo "         -o, --output-csv PATH   : CSV export destination path (default: output/decision_output.csv)"

# ==============================================================================
# 🛠️ Setup, Maintenance & Quality
# ==============================================================================
# Installs the package and its development dependencies in editable mode.
install:
	$(PYTHON) -m pip install -e .[dev]

# Automatically formats code with Black and fixes linting/imports with Ruff.
format:
	@echo "Formatting code (black)..."
	$(PYTHON) -m black $(ALL_SOURCES)
	@echo "Fixing lint issues and sorting imports (ruff)..."
	$(PYTHON) -m ruff check --fix $(ALL_SOURCES)

# Runs code formatting verification, Ruff linting, and Mypy static type checking.
lint:
	@echo "Running formatter check (black)..."
	$(PYTHON) -m black --check $(ALL_SOURCES)
	@echo "Running linter (ruff)..."
	$(PYTHON) -m ruff check $(ALL_SOURCES)
	@echo "Running static type checker (mypy)..."
	PYTHONPATH=src $(PYTHON) -m mypy $(SOURCES)

# Executes static security vulnerability analysis (Bandit) and dependency checks (Pip-Audit).
security-check:
	@echo "Running SAST security scan (bandit)..."
	$(PYTHON) -m bandit -r $(SOURCES)
	@echo "Checking dependencies for vulnerabilities (pip-audit)..."
	$(PYTHON) -m pip_audit

# Runs unit tests using Pytest with branch coverage reporting.
test:
	@echo "Running unit tests with coverage..."
	PYTHONPATH=src $(PYTHON) -m pytest --cov=src --cov=main --cov-report=term-missing $(TESTS_DIR)

# Orchestrates the full CI quality gate combining linting, security checks, and unit tests.
quality: lint security-check test

# Cleans temporary Python compilation cache files, test reports, and local caches.
clean:
	@echo "Cleaning Python temporary cache files and test reports..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -f data/etf_cache.json

# ==============================================================================
# 📈 Project Utils
# ==============================================================================
# Migrates legacy JSON portfolio and history datasets into the central SQLite database.
migrate:
	PYTHONPATH=. $(PYTHON) src/migrate_json_to_sqlite.py

# Pushes local configuration files to the remote Google Drive repository.
push-config:
	PYTHONPATH=src $(PYTHON) main.py push-config

# Pulls configuration files from the remote Google Drive repository to local storage.
pull-config:
	PYTHONPATH=src $(PYTHON) main.py pull-config

# Synchronizes portfolio data by executing JSON to SQLite migration and pushing configs to Google Drive.
sync-portfolio:
	PYTHONPATH=. $(PYTHON) src/migrate_json_to_sqlite.py
	PYTHONPATH=src $(PYTHON) main.py push-config

# Calculates and displays the current real-time valuation of the portfolio.
get-snapshot:
	PYTHONPATH=src $(PYTHON) main.py get-snapshot

# Computes portfolio valuation, records a historical snapshot in SQLite, and backs up to Google Drive.
save-snapshot:
	PYTHONPATH=src $(PYTHON) main.py save-snapshot

# Analyzes individual asset performance, absolute gains, and global Return on Investment (ROI).
analyze:
	PYTHONPATH=src $(PYTHON) main.py analyze

# Inspects detailed composition, TER, holdings, and sector/country breakdowns for an ETF.
etf-details:
	PYTHONPATH=src $(PYTHON) main.py etf-details $(ISIN)

# Inspects fundamental financial metrics for a stock ticker or ISIN.
stock-details:
	PYTHONPATH=src $(PYTHON) main.py stock-details $(TICKER)

# Analyzes consolidated portfolio sector and country exposure across active ETF holdings.
analyze-exposure:
	PYTHONPATH=src $(PYTHON) main.py analyze-exposure

# Synchronizes fundamental history snapshots for both stocks and ETFs into SQLite history.
sync-fundamentals:
	PYTHONPATH=src $(PYTHON) main.py sync-fundamentals

# Orchestrates portfolio decision ranking, quantitative scoring, and Google Gemini AI rebalancing analysis.
# Accepts optional CLI flags via FLAGS variable (e.g., make decision FLAGS="--skip-ai -v"):
#   -t, --targets-file PATH : Path to wishlist targets JSON file (default: data/portfolio_targets.json)
#   -p, --portfolio-file PATH: Path to active holdings JSON file (default: data/portfolio.json)
#   --skip-ai               : Run quantitative scoring matrix only (bypasses Gemini AI analysis)
#   -v, --verbose           : Display granular factor score breakdowns (Dip Sc, Cost Sc, Gap Sc)
#   -o, --output-csv PATH   : CSV export destination path (default: output/decision_output.csv)
decision:
	PYTHONPATH=src $(PYTHON) -m cli.decision --skip-ai