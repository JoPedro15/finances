# Makefile for the finances project

# Use python3 as the default interpreter
PYTHON = python3

# Define the source files to be checked
SOURCES = main.py utils/
TESTS_DIR = tests/
ALL_SOURCES = $(SOURCES) $(TESTS_DIR)

.PHONY: help install format check security-check test quality clean get-snapshot save-snapshot analyze

# ==============================================================================
# 📖 Help
# ==============================================================================
help:
	@echo "Available commands:"
	@echo "  --- Setup, Maintenance & Quality ---"
	@echo "  make install        - Installs dependencies."
	@echo "  make format         - Formats code automatically (black)."
	@echo "  make check          - Runs formatter check (black), linter (flake8) and type checker (mypy)."
	@echo "  make security-check - Runs security analysis (bandit & pip-audit)."
	@echo "  make test           - Runs unit tests (pytest)."
	@echo "  make quality        - Runs full quality gate (check + security-check + test)."
	@echo "  make clean          - Cleans Python temporary cache files and coverage reports."
	@echo "  --- Project Utils ---"
	@echo "  make get-snapshot   - Displays the current portfolio value."
	@echo "  make save-snapshot  - Saves the current portfolio value to history."
	@echo "  make analyze        - Analyzes overall portfolio performance."

# ==============================================================================
# 🛠️ Setup, Maintenance & Quality
# ==============================================================================
install:
	$(PYTHON) -m pip install -r requirements.txt

format:
	@echo "Formatting code (black)..."
	$(PYTHON) -m black $(ALL_SOURCES)

check:
	@echo "Running formatter check (black)..."
	$(PYTHON) -m black --check $(ALL_SOURCES)
	@echo "Running linter (flake8)..."
	$(PYTHON) -m flake8 $(ALL_SOURCES)
	@echo "Running static type checker (mypy)..."
	$(PYTHON) -m mypy $(SOURCES)

security-check:
	@echo "Running SAST security scan (bandit)..."
	$(PYTHON) -m bandit -r $(SOURCES)
	@echo "Checking dependencies for vulnerabilities (pip-audit)..."
	$(PYTHON) -m pip_audit -r requirements.txt

test:
	@echo "Running unit tests with coverage..."
	$(PYTHON) -m pytest --cov=utils --cov-report=html --cov-report=term $(TESTS_DIR)

quality: check security-check test

clean:
	@echo "Cleaning Python temporary cache files and test reports..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete

# ==============================================================================
# 📈 Project Utils
# ==============================================================================
get-snapshot:
	$(PYTHON) main.py get-snapshot

save-snapshot:
	$(PYTHON) main.py save-snapshot

analyze:
	$(PYTHON) main.py analyze