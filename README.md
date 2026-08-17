# 📈 Finances Portfolio Tracker

![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![CI Quality Pipeline](https://github.com/JoPedro15/finances/actions/workflows/ci.yml/badge.svg?branch=main)
<br />
![Formatter](https://img.shields.io/badge/formatter-Black-000000?style=flat-square&logo=python&logoColor=white)
![Linter](https://img.shields.io/badge/linter-Ruff-000000?style=python&logoColor=white)
![Security](https://img.shields.io/badge/security-Bandit%20%7C%20Audit-44cc11?style=flat-square&logo=shield&logoColor=white)
![GNU Make](https://img.shields.io/badge/env-GNU%20Make-active?style=flat-square&logo=gnu-make&logoColor=white)
<br />
![Stack](https://img.shields.io/badge/stack-yfinance%20%7C%20Typer%20%7C%20pytest%20%7C%20mypy-FF9900?style=flat-square&logo=python&logoColor=white)
![MIT License](https://img.shields.io/badge/license-MIT-607D8B?style=flat-square)

The **Finances Portfolio Tracker** is a lightweight, production-grade CLI application designed to track, record, analyze personal investment portfolios, and monitor target asset dip opportunities.

By integrating live market data with multi-currency conversion, concurrent API fetching, structured domain models, and centralized environment configuration, this project provides a **Single Source of Truth (SSoT)** for evaluating asset performance, portfolio ROI, and capital allocation.

## 🏗️ Architecture & Structure

The repository follows a clean modular design, strictly separating portfolio datasets, domain processing logic, data persistence layers, and execution utilities.

| Layer | Path | Description |
| :--- | :--- | :--- |
| `Data Storage` | `data/` | Centralized repository for asset holdings (`portfolio.json`), historical snapshots (`history.json`), and target watchlist (`watchlist.json`). |
| `Core Domain` | `src/core/` | Financial quotation retrieval, multi-currency conversion, snapshot management, performance analysis, price dip detection, domain models, and repository abstractions. |
| `Google Drive Integration` | `src/infra/gdrive/` | Infrastructure service and OAuth2 authentication handlers for remote backup capabilities. |
| `Logging System` | `src/utils/logger/` | Standardized internal logger enforcing clean output formatting across operations. |
| `Automation` | `.github/workflows/` | CI Quality Pipeline (`ci.yml`). |
| `Entrypoint` | `main.py` | Typer-powered CLI application orchestrating system commands and options. |
| `Tooling` | `root` | Modern project definitions (`pyproject.toml`), environment template (`.env.example`), and quality gates (`Makefile`). |

## 🔌 Core Modules (`src/core/`)

Each module inside `src/core/` adheres to standard type hinting, explicit domain exceptions, and modular design principles.

### 📐 Domain Models (`src/core/models.py`)
Defines strongly-typed, immutable dataclasses representing business concepts:
- **`Quotation`**: Represents ticker price, currency, and retrieval timestamp.
- **`Asset`**: Portfolio asset configuration (name, ISIN, ticker, quantity, buy price).
- **`AssetSnapshot` & `PortfolioSnapshot`**: Normalized valuations for individual assets and total portfolio state.

### ⚠️ Domain Exceptions (`src/core/exceptions.py`)
Custom error hierarchy eliminating generic exception handling:
- **`FinancesError`**: Base exception class.
- **`QuotationFetchError` / `ExchangeRateFetchError`**: Market data network or parsing issues.
- **`StorageReadError` / `StorageWriteError`**: I/O and persistence failures.
- **`InvalidWatchlistError`**: Malformed or unreadable watchlist configurations.

### 🗄️ Repository Abstraction (`src/core/repositories.py`)
Decouples domain logic from filesystem operations using Python Protocols:
- **`PortfolioRepository`**: Interface for loading asset definitions.
- **`HistoryRepository`**: Interface for reading and persisting portfolio snapshots.
- **`JsonPortfolioRepository` / `JsonHistoryRepository`**: Default JSON file implementations.

### ⚡ Parallel Processing & Snapshot Engine (`src/core/snapshot.py` & `src/core/dip_detector.py`)
Concurrent I/O execution powered by `ThreadPoolExecutor`:
- **Concurrent Quotes**: Multithreaded retrieval of asset prices and dip scans to reduce total execution time.
- **Exchange Normalization**: Dynamic fetching and caching of conversion rates via Yahoo Finance (default target: `EUR`).
- **Snapshot Persistence**: Appends timestamped valuation snapshots directly into storage via repositories.

### 📈 Performance Analyzer (`src/core/analysis.py`)
Computes overall portfolio health and asset metrics:
- **Asset Gain/Loss**: Calculates acquisition costs vs. current market values per ISIN.
- **Global ROI Analysis**: Determines global Return on Investment (ROI) based strictly on active snapshot assets.

## 💻 CLI Usage (`main.py`)

The application exposes a modern CLI built with **Typer**:

```bash
# Display current portfolio valuation
python main.py get-snapshot

# Calculate valuation and persist snapshot to history
python main.py save-snapshot

# Analyze portfolio performance and ROI
python main.py analyze

# Scan watchlist for price dips (with optional parameters)
python main.py check-dips --watchlist data/watchlist.json --min-drop 5.0 --max-drop 10.0 --lookback 5