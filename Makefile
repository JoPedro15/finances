# Makefile for the finances project

# Use python3 as the default interpreter
PYTHON = python3

# Define the source files to be checked
SOURCES = main.py utils/
TESTS_DIR = tests/

.PHONY: help install check security-check test quality clean get-snapshot save-snapshot analyze

# ==============================================================================
# 📖 Help
# ==============================================================================
help:
	@echo "Available commands:"
	@echo "  --- Setup, Maintenance & Quality ---"
	@echo "  make install        - Installs dependencies."
	@echo "  make check          - Runs formatter (black) and linter (flake8)."
	@echo "  make security-check - Runs security analysis (bandit & pip-audit)."
	@echo "  make test           - Runs unit tests (pytest)."
	@echo "  make quality        - Runs full quality gate (check + security-check + test)."
	@echo "  make clean          - Cleans Python cache files."
	@echo "  --- Project Utils ---"
	@echo "  make get-snapshot   - Displays the current portfolio value."
	@echo "  make save-snapshot  - Saves the current portfolio value to history."
	@echo "  make analyze        - Analyzes overall portfolio performance."

# ==============================================================================
# 🛠️ Setup, Maintenance & Quality
# ==============================================================================
install:
	$(PYTHON) -m pip install -r requirements.txt

check:
	@echo "Running formatter (black)..."
	$(PYTHON) -m black --check $(SOURCES)
	@echo "Running linter (flake8)..."
	$(PYTHON) -m flake8 $(SOURCES)

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
	@echo "Cleaning Python temporary cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# ==============================================================================
# 📈 Project Utils
# ==============================================================================
get-snapshot:
	$(PYTHON) main.py get-snapshot

save-snapshot:
	$(PYTHON) main.py save-snapshot

analyze:
	$(PYTHON) main.py analyze