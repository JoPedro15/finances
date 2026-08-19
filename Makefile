# Use python3 as the default interpreter
PYTHON = python3

# Define the source files to be checked
SOURCES = main.py src/
TESTS_DIR = tests/
ALL_SOURCES = $(SOURCES) $(TESTS_DIR)

.PHONY: help install format lint security-check test quality clean sync-portfolio push-config pull-config get-snapshot save-snapshot analyze etf-details stock-details analyze-exposure migrate recommend

# ==============================================================================
# 📖 Help
# ==============================================================================
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
	@echo "  make recommend        - Ranks investment targets using live market data."

# ==============================================================================
# 🛠️ Setup, Maintenance & Quality
# ==============================================================================
install:
	$(PYTHON) -m pip install -e .[dev]

format:
	@echo "Formatting code (black)..."
	$(PYTHON) -m black $(ALL_SOURCES)
	@echo "Fixing lint issues and sorting imports (ruff)..."
	$(PYTHON) -m ruff check --fix $(ALL_SOURCES)

lint:
	@echo "Running formatter check (black)..."
	$(PYTHON) -m black --check $(ALL_SOURCES)
	@echo "Running linter (ruff)..."
	$(PYTHON) -m ruff check $(ALL_SOURCES)
	@echo "Running static type checker (mypy)..."
	PYTHONPATH=src $(PYTHON) -m mypy $(SOURCES)

security-check:
	@echo "Running SAST security scan (bandit)..."
	$(PYTHON) -m bandit -r $(SOURCES)
	@echo "Checking dependencies for vulnerabilities (pip-audit)..."
	$(PYTHON) -m pip_audit

test:
	@echo "Running unit tests with coverage..."
	PYTHONPATH=src $(PYTHON) -m pytest --cov=src --cov=main --cov-report=term-missing $(TESTS_DIR)

quality: lint security-check test

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
migrate:
	PYTHONPATH=. $(PYTHON) src/migrate_json_to_sqlite.py

push-config:
	PYTHONPATH=src $(PYTHON) main.py push-config

pull-config:
	PYTHONPATH=src $(PYTHON) main.py pull-config

sync-portfolio:
	PYTHONPATH=. $(PYTHON) src/migrate_json_to_sqlite.py
	PYTHONPATH=src $(PYTHON) main.py push-config

get-snapshot:
	PYTHONPATH=src $(PYTHON) main.py get-snapshot

save-snapshot:
	PYTHONPATH=src $(PYTHON) main.py save-snapshot

analyze:
	PYTHONPATH=src $(PYTHON) main.py analyze

etf-details:
	PYTHONPATH=src $(PYTHON) main.py etf-details $(ISIN)

stock-details:
	PYTHONPATH=src $(PYTHON) main.py stock-details $(TICKER)

analyze-exposure:
	PYTHONPATH=src $(PYTHON) main.py analyze-exposure

recommend:
	PYTHONPATH=src $(PYTHON) -m cli.recommend