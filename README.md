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
* **SQLite Repository Pattern**: Fully normalized relational schema storing assets, historical valuation snapshots, stock fundamental history, and decision audit logs.
* **Google Drive Backup (`GDriveService`)**: Non-blocking automated backup of `finances.db` upon saving portfolio snapshots, alongside bidirectional synchronization of configuration files (`portfolio.json`, `portfolio_targets.json`).

---

## CLI Reference & Usage

The application is controlled via a rich Typer CLI interface defined in `main.py` and modular command groups.

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

# Asset Inspection
# Inspect composition, TER, top holdings, and sector/country breakdowns for an ETF
python main.py etf-details IE00B4L5Y983

# Inspect fundamental metrics (P/E, Market Cap, Debt/Equity, analyst consensus) for a stock
python main.py stock-details AAPL

#Investment Decision & Rebalancing
# Run the full decision pipeline (Quantitative Scoring + Gemini AI Batch Analysis)
make decision

# Run with verbose factor score breakdown (Dip Sc, Cost Sc, Gap Sc)
python main.py decision --verbose

# Run in quantitative-only mode (bypassing AI analysis)
python main.py decision --skip-ai

# Cloud Configuration Sync
# Pull configuration files from Google Drive to local data directory
python main.py pull-config

# Push local configuration files to Google Drive
python main.py push-config
```

---

## Quality Gates & Testing Suite

The project enforces strict code quality standards, verified through automated GitHub Actions CI pipelines (`ci.yml).  

Run the complete quality check suite locally using GNU Make:  

```bash
make quality
```

The quality suite executes:
- Black: Code formatting check (`black --check`).
- Ruff: Fast Python linting and import sorting (`ruff check`).
- Mypy: Strict static type checking across all modules (`mypy`).
- Bandit: Security vulnerability scanning (`bandit`).
- Pip-Audit: Known dependency vulnerability auditing (`pip-audit`).
- Pytest: Unit test execution with rigorous branch coverage reporting (`pytest --cov=src).  

---

## License

Distributed under the MIT License.

Developed and maintained by **João Pedro** ([@JoPedro15](https://github.com/JoPedro15)).

> *Fueled by Espresso, CrossFit WODs, and powered by Gemini AI collaboration.* ☕🏋️‍♂️🤖
