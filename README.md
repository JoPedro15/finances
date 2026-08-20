# Finances Portfolio Tracker & Decision Engine

![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![Tests Coverage](https://img.shields.io/badge/coverage-93.94%25-44cc11?style=flat-square)
![CI Quality Pipeline](https://github.com/JoPedro15/finances/actions/workflows/ci.yml/badge.svg?branch=main)
<br />
![Formatter](https://img.shields.io/badge/formatter-Black-000000?style=flat-square&logo=python&logoColor=white)
![Linter](https://img.shields.io/badge/linter-Ruff-000000?style=python&logoColor=white)
![Security](https://img.shields.io/badge/security-Bandit%20%7C%20Audit-44cc11?style=flat-square&logo=shield&logoColor=white)
![GNU Make](https://img.shields.io/badge/env-GNU%20Make-active?style=flat-square&logo=gnu-make&logoColor=white)
<br />
![Stack](https://img.shields.io/badge/stack-yfinance%20%7C%25SQLite%20%7C%20Gemini%20AI%20%7C%20Typer%20%7C%20pytest-FF9900?style=flat-square&logo=python&logoColor=white)
![MIT License](https://img.shields.io/badge/license-MIT-607D8B?style=flat-square)

---

The **Finances Portfolio Tracker & Decision Engine** is an enterprise-grade command-line interface (CLI) application engineered to track personal investment portfolios, monitor market prices, analyze asset performance, and execute **deterministic multi-factor rebalancing powered by Google Gemini AI**.

Designed with a strict separation of concerns, this system serves as a **Single Source of Truth (SSoT)** for multi-asset portfolios (Stocks and ETFs), integrating real-time market data retrieval, multi-currency conversion, relational SQLite persistence, automated Google Drive cloud synchronization, and robust quantitative scoring strategies.

---

## Architectural Blueprint & Directory Structure

The repository follows a clean, modular architecture, segregating domain logic, infrastructure providers, decision engines, and presentation layers.

| Layer | Path | Description                                                                                                                            |
| :--- | :--- |:---------------------------------------------------------------------------------------------------------------------------------------|
| **Core Domain** | `src/core/` | Business logic, quotation retrieval, multi-currency exchange, snapshot management, performance analysis, and repository protocols.|
| **Decision Engine** | `src/core/decision/` | Strategy pattern orchestrating asset priority scoring (`dip_score`, `cost_score`, `allocation_score`) for stocks and ETFs.|
| **AI Infrastructure** | `src/infra/ai/` | Google Gemini API client executing robust batch structured JSON portfolio rebalancing analysis with Pydantic validation.|
| **Database & Schema** | `src/infra/database/` | SQLite connection management, foreign key enforcement, transactional contexts, and relational schema DDL.|
| **Cloud Synchronization** | `src/infra/gdrive/` | Google Drive service wrapper and OAuth2 authentication handler for automated remote database backups and config sync.|
| **JustETF Scraper** | `src/infra/justetf/` | Scraper client extracting ETF composition, sector weights, geographic allocation, and TER directly from JustETF profile pages.|
| **CLI & Automation** | `src/cli/` & `root` | Typer-powered CLI interface (`main.py`, `recommend`) and GNU Make automation workflows.|

---

## Core Modules & Technical Highlights

### 1. Deterministic Decision Engine (`src/core/decision/`)
Rather than relying purely on opaque LLM predictions, the engine uses explicit quantitative models implementing the Strategy Pattern:
* **Stock Scoring Strategy (`stock_strategy.py`)**: Evaluates price pullbacks from 52-week highs (with *falling knife* protection), forward vs. trailing P/E growth ratios, and 52-week range positioning.
* **ETF Scoring Strategy (`etf_strategy.py`)**: Combines technical discount sweet-spots, cost efficiency via Total Expense Ratio (TER), and underwriting allocation gaps.
* **Composite Priority**: Combines weighted sub-scores into a normalized total score (`total_score`) to rank target wishlist assets objectively.

### 2. Gemini AI Batch Advisory (`src/infra/ai/`)
* **Enterprise Client (`GeminiClient`)**: Integrates with the Google GenAI SDK, featuring exponential backoff retry mechanisms for transient errors and quotas.
* **Batch Portfolio Analysis**: Processes the entire target asset wishlist in a single optimized API call, returning strict structured JSON validated through Pydantic (`BatchRebalanceRecommendations`).
* **Graceful Degradation**: Automatically falls back to the pure quantitative matrix if AI quotas are exhausted or credentials are unconfigured.

### 3. Data Providers & Web Scraping (`src/core/providers.py` & `src/infra/justetf/`)
* **`StockProvider`**: Fetches real-time equity quotations, currency conversions, and fundamental metrics (`StockDetails`) via `yfinance`.
* **`ETFProvider`**: Combines real-time price feeds with structured composition data extracted by `JustETFClient`, leveraging local TTL-based caching (`etf_cache.json`) to minimize network overhead.

### 4. Relational Persistence & Cloud Sync (`src/infra/database/` & `src/infra/gdrive/`)
* **SQLite Repository Pattern**: Fully normalized relational schema storing assets, historical valuation snapshots, stock fundamental history, and decision audit logs[cite: 31, 34].
* **Google Drive Backup (`GDriveService`)**: Non-blocking automated backup of `finances.db` upon saving portfolio snapshots, alongside bidirectional synchronization of configuration files (`portfolio.json`, `portfolio_targets.json`)[cite: 32, 36, 43].

---

## CLI Reference & Usage

The application is controlled via a rich Typer CLI interface defined in `main.py` and modular command groups[cite: 21, 43].

### Portfolio Monitoring & Valuation
```bash
# Calculate and display current portfolio valuation and asset distribution
python main.py get-snapshot

# Calculate valuation, persist a timestamped snapshot to SQLite, and backup to Google Drive
python main.py save-snapshot

# Analyze historical asset performance, absolute gains, and global ROI
python main.py analyze

# Analyze consolidated portfolio sector and country exposure across active ETFs
python main.py analyze-exposure





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

### CSV Export Engine
- **`export_to_csv`**: Serializes decision matrices (including quantitative sub-scores, target allocations, and AI recommendations) into structured CSV files (`output/decision_output.csv`).

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
# Run full decision pipeline (Quantitative Scoring + Gemini AI Analysis)
make decision
# or via python module:
PYTHONPATH=src python3 -m cli.decision

# Display detailed factor breakdown columns (Dip Sc, Cost Sc, Gap Sc)
make decision FLAGS="-v"

# Run in quantitative-only mode (bypassing AI analysis)
make decision FLAGS="--skip-ai"

# Export decision matrix to custom CSV path
make decision FLAGS="-o output/decision_output.csv"
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