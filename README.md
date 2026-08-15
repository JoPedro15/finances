# 📈 Finances Portfolio Tracker

![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![CI Quality Pipeline](https://github.com/JoPedro15/finances/actions/workflows/ci.yml/badge.svg?branch=main)
<br />
![Formatter](https://img.shields.io/badge/formatter-Black-000000?style=flat-square&logo=python&logoColor=white)
![Linter](https://img.shields.io/badge/linter-Flake8-000000?style=flat-square&logo=python&logoColor=white)
![Security](https://img.shields.io/badge/security-Bandit%20%7C%20Audit-44cc11?style=flat-square&logo=shield&logoColor=white)
![GNU Make](https://img.shields.io/badge/env-GNU%20Make-active?style=flat-square&logo=gnu-make&logoColor=white)
<br />
![Stack](https://img.shields.io/badge/stack-yfinance%20%7C%20pytest-FF9900?style=flat-square&logo=python&logoColor=white)
![MIT License](https://img.shields.io/badge/license-MIT-607D8B?style=flat-square)

The **Finances Portfolio Tracker** is a lightweight, production-grade CLI application designed to track, record, and analyze personal investment portfolios.

By integrating live market data with multi-currency conversion and historical record-keeping, this project provides a **Single Source of Truth (SSoT)** for evaluating asset performance, portfolio ROI, and capital gains.

## 🏗️ Architecture & Structure

The repository follows a clean modular design, strictly separating portfolio datasets, domain processing logic, and execution utilities.

| Layer | Path | Description |
| :--- | :--- | :--- |
| `Data Storage` | `data/` | Centralized repository for asset definitions (`portfolio.json`) and snapshot records (`history.json`). |
| `Core Utilities` | `utils/` | Financial quotation retrieval, multi-currency conversion, snapshot management, and performance analysis. |
| `Logging System` | `utils/logger/` | Standardized internal logger enforcing clean output formatting across operations. |
| `Entrypoint` | `main.py` | CLI command router orchestrating system execution modes. |
| `Tooling` | `root` | Dependency definitions (`requirements.txt`), linter rules (`.flake8`), and quality gates (`Makefile`). |

## 🔌 Core Utilities (utils/)

Each module inside `utils/` adheres to standard type hinting and modular design principles.

### 📊 Snapshot Manager (`utils/snapshot.py`)

Handles real-time value evaluation and multi-currency normalization:
- **Exchange Normalization**: Dynamic fetching and caching of conversion rates via Yahoo Finance (default target: `EUR`).
- **Snapshot Persistence**: Appends timestamped valuation snapshots directly into `data/history.json`.

### 📈 Performance Analyzer (`utils/analysis.py`)

Computes overall portfolio health and asset metrics:
- **Asset Gain/Loss**: Calculates acquisition costs vs. current market values per ISIN.
- **Global ROI Analysis**: Determines global Return on Investment (ROI) based strictly on active snapshot assets.

### 💰 Quotation Engine (`utils/get_quotation.py`)

Market data retrieval wrapper powered by `yfinance`:
- **Real-Time Quotes**: Fetches latest ticker price and native currency.
- **Currency Exchange**: Resolves dynamic currency exchange pairs (e.g., `USDEUR=X`, `GBPEUR=X`).

## 🛠️ Global Quality Gate (GNU Make)

A unified orchestration layer ensures parity between local development and CI/CD pipelines.

| Command | Description |
| :--- | :--- |
| `make install` | Installs all core, linting, security, and test dependencies. |
| `make get-snapshot` | Displays current portfolio valuation without modifying history records. |
| `make save-snapshot` | Evaluates portfolio value and appends a timestamped entry to `data/history.json`. |
| `make analyze` | Analyzes total ROI and individual asset acquisition vs. market performance. |
| `make check` | Runs code formatting (`black --check`) and linting (`flake8`). |
| `make sec-check` | Executes SAST security scan (`bandit`) and dependency audit (`pip-audit`). |
| `make test` | Runs unit test suite (`pytest`). |
| `make quality` | Executes the complete quality gate (`check` + `sec-check` + `test`). |
| `make clean` | Removes temporary Python caches and build artifacts. |

## 📖 Governance & Standards

To maintain codebase integrity, contributions must adhere to the project's engineering standards:

- **Type Safety**: Explicit type annotations are required for all function signatures and local variables.
- **Documentation**: Code comments, docstrings, variable names, and READMEs must be written in English.
- **Zero-Print Policy**: Direct `print()` statements are avoided in favor of the structured logger module.
- **Security & Quality**: All PRs must pass SAST scans, dependency vulnerability audits, and unit tests.

---

João Pedro | Automation Engineer <br /> [GitHub profile](https://github.com/JoPedro15)