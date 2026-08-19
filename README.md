# Finances Portfolio Tracker & Decision Engine

![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![CI Quality Pipeline](https://github.com/JoPedro15/finances/actions/workflows/ci.yml/badge.svg?branch=main)
<br />
![Formatter](https://img.shields.io/badge/formatter-Black-000000?style=flat-square&logo=python&logoColor=white)
![Linter](https://img.shields.io/badge/linter-Ruff-000000?style=python&logoColor=white)
![Security](https://img.shields.io/badge/security-Bandit%20%7C%20Audit-44cc11?style=flat-square&logo=shield&logoColor=white)
![GNU Make](https://img.shields.io/badge/env-GNU%20Make-active?style=flat-square&logo=gnu-make&logoColor=white)
<br />
![Stack](https://img.shields.io/badge/stack-yfinance%20%7C%20SQLite%20%7C%20Gemini%20AI%20%7C%20Typer%20%7C%20pytest-FF9900?style=flat-square&logo=python&logoColor=white)
![MIT License](https://img.shields.io/badge/license-MIT-607D8B?style=flat-square)

The **Finances Portfolio Tracker** is a CLI application designed to track, record, analyze personal investment portfolios, monitor target asset dip opportunities, and execute AI-assisted rebalancing.

By integrating live market data with multi-currency conversion, concurrent API fetching, relational SQLite persistence, structured domain models, automated Google Drive cloud synchronization, **deterministic multi-factor asset scoring**, and **Gemini AI batch rebalancing**, this project provides a **Single Source of Truth (SSoT)** for evaluating asset performance, portfolio ROI, and capital allocation decisions.

---

## Architecture & Structure

The repository follows a clean, modular design, strictly separating portfolio datasets, domain processing logic, decision engines, persistence layers, remote backups, and CLI execution interfaces.

| Layer | Path | Description |
| :--- | :--- | :--- |
| `Data Storage` | `data/` | SQLite database (`finances.db`), portfolio holdings (`portfolio.json`), target wishlist (`portfolio_targets.json`), watchlist configuration (`watchlist.json`), and ETF metadata cache (`etf_cache.json`). |
| `Outputs` | `output/` | Exported analytical decision matrices and CSV reports (`recommend_output.csv`). |
| `Core Domain` | `src/core/` | Financial quotation retrieval, multi-currency conversion, snapshot management, performance analysis, price dip detection, domain models, data provider abstractions (`providers.py`), and repository protocols. |
| `Decision Engine` | `src/core/decision/` | Strategy pattern scoring engine (`engine.py`) calculating composite asset priority scores (`dip_score`, `cost_score`, `allocation_score`). |
| `AI Infrastructure` | `src/infra/ai/` | Google Gemini API client (`client.py`) executing batch structured JSON portfolio rebalancing analysis with Pydantic validation. |
| `Database Infrastructure` | `src/infra/database/` | SQLite connection management (`connection.py`), foreign key enforcement, transactional contexts, and schema initialization DDL (`schema.py`). |
| `Google Drive Integration` | `src/infra/gdrive/` | Remote synchronization service (`service.py`) and OAuth2 authentication handler (`auth.py`) for automated database backups and bidirectional config file sync. |
| `JustETF Integration` | `src/infra/justetf/` | Scraper client extracting ETF composition, sector allocation, country exposure, and TER directly from JustETF profile pages. |
| `Notifications` | `src/infra/notifications/` | Webhook dispatchers (`discord.py`) sending rebalancing recommendations and decision matrices to Discord channels. |
| `Logging System` | `src/utils/logger/` | Standardized internal logger enforcing clean output formatting across operations. |
| `Data Migration` | `src/migrate_json_to_sqlite.py` | Idempotent migration utility transferring legacy JSON datasets into the SQLite database engine. |
| `Secrets & Credentials` | `secrets/` | Isolated local directory storing sensitive OAuth2 client secrets (`credentials.json`) and active tokens (`token.json`). |
| `Automation` | `.github/workflows/` | CI Quality Pipeline (`ci.yml`). |
| `Rebalancing CLI` | `src/cli/recommend.py` | Typer-powered CLI command orchestrating market data enrichment, quantitative scoring, Gemini AI rebalancing, and CSV exports. |
| `Main CLI Entrypoint` | `main.py` | Primary CLI application orchestrating system tracking commands and options. |
| `Tooling` | `root` | Modern project definitions (`pyproject.toml`), environment template (`.env.example`), and quality gates (`Makefile`). |

---

## Core Modules (`src/core/` & `src/infra/`)

Each module adheres to standard type hinting, explicit domain exceptions, and modular design principles.

### Domain Models (`src/core/models.py`)
Defines strongly-typed, immutable dataclasses representing business concepts:
- **`Quotation`**: Represents ticker price, currency, and retrieval timestamp.
- **`Asset`**: Portfolio asset configuration (name, ISIN, ticker, quantity, buy price, asset type).
- **`AssetSnapshot` & `PortfolioSnapshot`**: Normalized valuations for individual assets and total portfolio state.
- **`Holding`**, **`SectorExposure`**, **`CountryExposure`** & **`ETFDetails`**: Consolidated ETF composition, sector, country allocations, and TER.
- **`StockDetails`**: Fundamental equity metrics (Market Cap, P/E Ratio, Forward P/E, Dividend Yield, 52-week High/Low, Sector, and Industry).
- **`RebalanceRecommendation`**: Structured AI recommendation schema containing recommended action (`BUY`/`SELL`/`HOLD`), urgency level, confidence score, risk score, valuation score, and reasoning text.

### Data Providers (`src/core/providers.py`)
Implements the `AssetDataProvider` protocol to decouple market data sources:
- **`StockProvider`**: Fetches real-time stock prices and fundamental metrics (`StockDetails`) via `yfinance`.
- **`ETFProvider`**: Combines real-time price quotes from `yfinance` with ETF composition details scraped from JustETF (cached locally).

### Database Infrastructure & Repositories (`src/infra/database/` & `src/core/repositories.py`)
Decouples domain logic from database persistence using Python Protocols:
- **`SqlitePortfolioRepository`**: Default SQLite implementation for loading and persisting portfolio asset configurations.
- **`SqliteHistoryRepository`**: Default SQLite implementation for reading and recording timestamped valuation snapshots.
- **`ETFCacheRepository`**: Interface for reading and persisting cached ETF composition and exposure details with TTL validation.

### Deterministic Decision Engine (`src/core/decision/`)
Implements the Strategy Pattern to evaluate target wishlist assets dynamically without black-box opacity:
- **`StockScoringStrategy` & `EtfScoringStrategy`**: Concrete scoring rules for equities and ETFs.
- **Factor Breakdown (`AssetScore`)**:
  - **`dip_score`**: Quantifies price pullbacks from 52-week peak values.
  - **`cost_score`**: Penalizes high TER (for ETFs) or high valuation multiples (P/E ratios for stocks).
  - **`allocation_score`**: Measures target allocation gap relative to current portfolio weighting.
- **Composite Score**: Weighted sum producing a normalized total priority score for asset ranking.

### Gemini AI Batch Rebalancing (`src/infra/ai/`)
Provides LLM advisory insights integrated directly into the quantitative decision matrix:
- **`GeminiClient`**: Enterprise client wrapping the Google GenAI SDK with structured JSON parsing via Pydantic (`BatchRebalanceRecommendations`).
- **Batch Processing**: Evaluates the entire target asset wishlist in a single API request to optimize quota usage.
- **Graceful Fallback**: Catches `GeminiQuotaError` (e.g., HTTP 429 `RESOURCE_EXHAUSTED`) and API failures, falling back seamlessly to displaying the quantitative decision matrix.

### Google Drive Cloud Backup & Sync (`src/infra/gdrive/`)
Provides non-blocking remote synchronization and backup capabilities:
- **`GDriveService`**: Handles downloading, uploading, and checking files against target Google Drive folders.
- **Automated Database Backups**: Automatically backs up the relational database (`finances.db`) to Google Drive upon executing `save-snapshot`.
- **Bidirectional Config Sync**: Downloads and uploads JSON configuration files (`portfolio.json`, `watchlist.json`) between local storage and Google Drive.

### Discord Notifications (`src/infra/notifications/`)
- **`send_discord_notification`**: Formats and dispatches rebalancing recommendation matrices and actionable AI advisory alerts directly to Discord webhooks.

### CSV Export Engine
- **`export_to_csv`**: Serializes decision matrices (including quantitative sub-scores, target allocations, and AI recommendations) into structured CSV files (`output/recommend_output.csv`).

### Domain Exceptions (`src/core/exceptions.py`)
Custom error hierarchy eliminating generic exception handling:
- **`FinancesError`**: Base exception class.
- **`QuotationFetchError` / `ExchangeRateFetchError`**: Market data network or parsing issues.
- **`StorageReadError` / `StorageWriteError`**: I/O and database persistence failures.
- **`InvalidWatchlistError`**: Malformed or unreadable watchlist configurations.
- **`JustETFScrapeError`**: Network or HTML parsing issues during JustETF data extraction.
- **`GeminiAuthError` / `GeminiAPIError` / `GeminiQuotaError` / `GeminiParsingError`**: Dedicated errors for LLM authentication, API failure, quota exhaustion, and structured schema parsing errors.

### Parallel Processing & Snapshot Engine (`src/core/snapshot.py` & `src/core/dip_detector.py`)
Concurrent I/O execution powered by `ThreadPoolExecutor`:
- **Concurrent Quotes**: Multithreaded retrieval of asset prices and dip scans to reduce total execution time.
- **Exchange Normalization**: Dynamic fetching and caching of conversion rates via Yahoo Finance (default target: `EUR`).
- **Database Persistence**: Appends timestamped valuation snapshots directly into the SQLite database.

### Performance Analyzer (`src/core/analysis.py`)
Computes overall portfolio health and asset metrics:
- **Asset Gain/Loss**: Calculates acquisition costs vs. current market values per ISIN.
- **Global ROI Analysis**: Determines global Return on Investment (ROI) based strictly on active snapshot assets.
- **Portfolio Exposure**: Calculates weighted sector and country breakdown across active portfolio ETFs.

---

## CLI Usage

### Rebalancing & Investment Recommendation CLI (`cli/recommend.py`)

```bash
# Run full rebalancing pipeline (Quantitative Scoring + Gemini AI Analysis)
make recommend
# or via python module:
PYTHONPATH=src python3 -m cli.recommend

# Display detailed factor breakdown columns (Dip Sc, Cost Sc, Gap Sc)
PYTHONPATH=src python3 -m cli.recommend -v

# Run in quantitative-only mode (bypassing AI analysis)
PYTHONPATH=src python3 -m cli.recommend --skip-ai

# Export decision matrix to CSV (Defaults to output/recommend_output.csv)
PYTHONPATH=src python3 -m cli.recommend -o output/recommend_output.csv

# Dispatch rebalancing recommendations to Discord webhook
PYTHONPATH=src python3 -m cli.recommend --notify
```

### Portfolio Management & Snapshot CLI (`main.py`)

```bash
# Pull configuration files (portfolio.json, watchlist.json) from Google Drive to local data directory
python main.py pull-config

# Push local configuration files (portfolio.json, watchlist.json) to Google Drive
python main.py push-config

# Migrate legacy JSON data (portfolio.json / history.json) to SQLite database
make migrate
# or manually:
PYTHONPATH=. python3 src/migrate_json_to_sqlite.py

# Display current portfolio valuation
python main.py get-snapshot

# Calculate valuation, persist snapshot to SQLite history, and back up database to Google Drive
python main.py save-snapshot

# Analyze portfolio performance and ROI
python main.py analyze

# Scan watchlist for price dips (with optional parameters)
python main.py check-dips --watchlist data/watchlist.json --min-drop 5.0 --max-drop 10.0 --lookback 5

# Inspect composition, TER, and holdings for a specific ETF or all portfolio ETFs
python main.py etf-details IE00B4L5Y983

# Inspect fundamental metrics (Market Cap, P/E Ratio, Sector, etc.) for a stock or all portfolio stocks
python main.py stock-details AAPL

# Analyze consolidated portfolio exposure across sectors and countries
python main.py analyze-exposure
```

___

## Quality Gates & Automation

Run the comprehensive quality check suite before committing or opening a Pull Request:

```bash
make quality
```

The `Makefile` target executes:

`black --check`: Code formatting validation.

`ruff check`: Fast Python linting and import sorting.

`mypy`: Strict static type checking across all modules.

`bandit`: Security vulnerability scanning.

`pip-audit`: Known dependency vulnerability auditing.

`pytest`: Unit test execution with coverage reporting (`--cov=src`).

---

Developed and maintained by **João Pedro** ([@JoPedro15](https://github.com/JoPedro15)).

> *Fueled by Espresso, CrossFit WODs, and powered by Gemini AI collaboration.* ☕🏋️‍♂️🤖