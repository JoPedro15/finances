# 📈 Finances Portfolio Tracker

![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![CI Quality Pipeline](https://github.com/JoPedro15/finances/actions/workflows/ci.yml/badge.svg?branch=main)
<br />
![Formatter](https://img.shields.io/badge/formatter-Black-000000?style=flat-square&logo=python&logoColor=white)
![Linter](https://img.shields.io/badge/linter-Flake8-000000?style=flat-square&logo=python&logoColor=white)
![Security](https://img.shields.io/badge/security-Bandit%20%7C%20Audit-44cc11?style=flat-square&logo=shield&logoColor=white)
![GNU Make](https://img.shields.io/badge/env-GNU%20Make-active?style=flat-square&logo=gnu-make&logoColor=white)
<br />
![Stack](https://img.shields.io/badge/stack-yfinance%20%7C%20pytest%20%7C%20dotenv-FF9900?style=flat-square&logo=python&logoColor=white)
![MIT License](https://img.shields.io/badge/license-MIT-607D8B?style=flat-square)

The **Finances Portfolio Tracker** is a lightweight, production-grade CLI application designed to track, record, analyze personal investment portfolios, and monitor target asset dip opportunities.

By integrating live market data with multi-currency conversion, historical record-keeping, and centralized environment configuration, this project provides a **Single Source of Truth (SSoT)** for evaluating asset performance, portfolio ROI, and capital allocation.

## 🏗️ Architecture & Structure

The repository follows a clean modular design, strictly separating portfolio datasets, domain processing logic, automation workflows, and execution utilities.

| Layer | Path | Description |
| :--- | :--- | :--- |
| `Data Storage` | `data/` | Centralized repository for asset holdings (`portfolio.json`), historical snapshots (`history.json`), and target watchlist (`watchlist.json`). |
| `Core Utilities` | `utils/` | Financial quotation retrieval, multi-currency conversion, snapshot management, performance analysis, price dip detection, and central configuration. |
| `Logging System` | `utils/logger/` | Standardized internal logger enforcing clean output formatting across operations. |
| `Automation` | `.github/workflows/` | CI Quality Pipeline (`ci.yml`). |
| `Entrypoint` | `main.py` | CLI command router orchestrating system execution modes. |
| `Tooling` | `root` | Dependency definitions (`requirements.txt`), environment template (`.env.example`), linter rules (`.flake8`), and quality gates (`Makefile`). |

## 🔌 Core Utilities (utils/)

Each module inside `utils/` adheres to standard type hinting, strict error handling, and modular design principles.

### ⚙️ Central Configuration (`utils/config.py`)

Centralized Single Source of Truth (SSoT) for strategy parameters and environment variables:
- **`python-dotenv` Integration**: Loads local `.env` variables seamlessly during local runs.
- **Typed Dataclass**: Defines immutable defaults for dip detection thresholds (`min_drop_pct`, `max_drop_pct`, `lookback_days`).

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

### 📉 Dip Detector (`utils/dip_detector.py`)

Scans watchlist assets for potential buying opportunities:
- **Watchlist Ingestion**: Loads asset metadata (Name, ISIN, Ticker) from `data/watchlist.json`.
- **Peak Drop Analysis**: Identifies assets dropping within configurable percentage thresholds (`min_drop_pct` to `max_drop_pct`) from recent high peaks.

## ⚙️ Automated Workflows (GitHub Actions)

- **Continuous Integration (`ci.yml`)**: Executes formatting, linting, static type checking (`mypy`), security audits, and pytest suites on Python 3.13.

## 🛠️ Global Quality Gate (GNU Make)

A unified orchestration layer ensures parity between local development and CI/CD pipelines.

| Command | Description |
| :--- | :--- |
| `make install` | Installs all core, linting, security, and test dependencies (`requirements.txt`). |
| `make get-snapshot` | Displays current portfolio valuation without modifying history records. |
| `make save-snapshot` | Evaluates portfolio value and appends a timestamped entry to `data/history.json`. |
| `make analyze` | Analyzes total ROI and individual asset acquisition vs. market performance. |
| `make check-dips` | Scans watchlist for stock price dip opportunities and logs findings to stdout. |
| `make check` | Runs code formatting (`black --check`), linting (`flake8`), and type checking (`mypy`). |
| `make security-check` | Executes SAST security scan (`bandit`) and dependency audit (`pip-audit`). |
| `make test` | Runs unit test suite with coverage (`pytest`). |
| `make quality` | Executes the complete quality gate (`check` + `security-check` + `test`). |
| `make clean` | Removes temporary Python caches and build artifacts. |

## 📖 Governance & Standards

To maintain codebase integrity, contributions must adhere to the project's engineering standards:

- **Type Safety**: Explicit type annotations are required for all function signatures and local variables.
- **Documentation**: Code comments, docstrings, variable names, and READMEs must be written in English.
- **Zero-Print Policy**: Direct `print()` statements are avoided in favor of the structured logger module.
- **Security & Quality**: Secrets and runtime parameters are managed via `.env`. All PRs must pass SAST scans, dependency vulnerability audits, and unit tests with coverage.

---

João Pedro | Automation Engineer <br /> [GitHub profile](https://github.com/JoPedro15)