# Makefile for the finances project

# Use python3 as the default interpreter
PYTHON = python3

.PHONY: help install get-snapshot save-snapshot analyze

help:
	@echo "Available commands:"
	@echo "  make install        - Installs the required Python dependencies."
	@echo "  make get-snapshot   - Calculates and displays the current portfolio value."
	@echo "  make save-snapshot  - Calculates and saves the current portfolio value to the history file."
	@echo "  make analyze        - Analyzes the overall portfolio performance."

install:
	$(PYTHON) -m pip install -r requirements.txt

get-snapshot:
	$(PYTHON) main.py get-snapshot

save-snapshot:
	$(PYTHON) main.py save-snapshot

analyze:
	$(PYTHON) main.py analyze
