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
![Stack](https://img.shields.io/badge/stack-yfinance%20%7C%20SQLite%20%7C%20Gemini%203.6%20Flash%20%7C%20Typer%20%7C%20pytest-FF9900?style=flat-square&logo=python&logoColor=white)
![MIT License](https://img.shields.io/badge/license-MIT-607D8B?style=flat-square)

---

The **Finances Portfolio Tracker & Decision Engine** is an enterprise-grade command-line interface (CLI) application engineered to track personal investment portfolios, monitor market prices, analyze asset performance, and execute **deterministic multi-factor rebalancing powered by Google Gemini AI**.

Designed with a strict separation of concerns, this system leverages Google Drive as a **Cloud Single Source of Truth (SSoT)** for all dynamic data (`finances.db`, portfolios, targets, and caches), integrating real-time market data retrieval, multi-currency conversion, relational SQLite persistence, and quantitative scoring strategies.

---

## Architectural Blueprint & Directory Structure

The repository follows a clean, modular architecture, segregating domain logic, infrastructure providers, decision engines, and presentation layers.

| Layer | Path | Description |
| :--- | :--- | :--- |
| **Core Domain** | `src/core/` | Business logic, quotation retrieval, multi-currency exchange, snapshot management, performance analysis, and repository protocols. |
| **Decision Engine** | `src/core/decision/` | Strategy pattern orchestrating asset priority scoring (`dip_score`, `cost_score`, `allocation_score`) for stocks and ETFs. |
| **AI Infrastructure** | `src/infra/ai/` | Google Gemini API client (`gemini-3.6-flash`) executing robust batch structured JSON portfolio rebalancing analysis with Pydantic validation. |
| **Database & Schema** | `src/infra/database/` | SQLite connection management, foreign key enforcement, transactional contexts, and relational schema DDL. |
| **Cloud SSoT Engine** | `src/infra/gdrive/` | Google Drive service wrapper handling bidirectional synchronization of `finances.db` and configuration JSON files. |
| **JustETF Scraper** | `src/infra/justetf/` | Scraper client extracting ETF composition, sector weights, geographic allocation, and TER directly from JustETF profile pages. |
| **CLI & Automation** | `src/cli/` & `root` | Typer-powered CLI interface (`main.py`, `cli/`) and GNU Make automation workflows. |

---

## Core Modules & Technical Highlights

### 1. Deterministic Decision Engine (`src/core/decision/`)
Rather than relying purely on opaque LLM predictions, the engine uses explicit quantitative models implementing the Strategy Pattern:
* **Stock Scoring Strategy (`stock_strategy.py`)**: Evaluates price pullbacks from 52-week highs (with *falling knife* protection), forward vs. trailing P/E growth ratios, and 52-week range positioning.
* **ETF Scoring Strategy (`etf_strategy.py`)**: Combines technical discount sweet-spots, cost efficiency via Total Expense Ratio (TER), and target allocation gaps.
* **Composite Priority**: Combines weighted sub-scores into a normalized total score (`total_score`) to rank target wishlist assets objectively.

### 2. Gemini AI Batch Advisory (`src/infra/ai/`)
* **Enterprise Client (`GeminiClient`)**: Powered by `gemini-3.6-flash` via the Google GenAI SDK, featuring exponential backoff retry mechanisms for transient errors and quotas.
* **Batch Portfolio Analysis**: Processes the entire target asset wishlist in a single API call, returning strict structured JSON validated through Pydantic (`BatchRebalanceRecommendations`).
* **Graceful Fallback**: Automatically falls back to the quantitative decision matrix if AI quotas are exhausted or credentials are unconfigured.

### 3. Data Providers & Web Scraping (`src/core/providers.py` & `src/infra/justetf/`)
* **`StockProvider`**: Fetches real-time equity quotations, currency conversions, and fundamental metrics (`StockDetails`) via `yfinance`.
* **`ETFProvider`**: Combines real-time price feeds with structured composition data extracted by `JustETFClient`, leveraging local TTL-based caching (`etf_cache.json`) to minimize network overhead.

### 4. Cloud SSoT Architecture (`src/infra/gdrive/`)
* **Stateless Local Environment**: The local `data/` directory is ephemeral and strictly ignored by Git (`.gitignore`).
* **Automated Bidirectional Sync**: At application startup, all required operational files (`finances.db`, `portfolio.json`, `portfolio_targets.json`, `etf_cache.json`, `system_instruction.json`) are automatically pulled from Google Drive.
* **Automated Persistence**: Any command generating or modifying data immediately pushes the updated state back to Google Drive upon process completion.

---

## Quickstart & Setup

1. **Clone repository and initialize environment**:

```bash
git clone https://github.com/JoPedro15/finances.git
cd finances
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Configure GCP credentials and environment variables**:

```bash
mkdir -p secrets
# Place your GCP OAuth credentials.json in secrets/credentials.json
cp .env.example .env
```

---

## Environment Variables & Configuration

Key configuration parameters in `.env`:

```ini
# Gemini AI Configuration
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.6-flash

# Google Drive Folders (Cloud SSoT)
GDRIVE_CLIENT_SECRET_FILE=secrets/credentials.json
GDRIVE_TOKEN_FILE=secrets/token.json
GDRIVE_CONFIG_FOLDER_ID=your_config_folder_id
GDRIVE_SNAPSHOT_FOLDER_ID=your_snapshot_folder_id
GDRIVE_REPORTS_FOLDER_ID=your_reports_folder_id
GDRIVE_DATABASE_FOLDER_ID=your_database_folder_id

# Scoring Strategy Weights (Must sum to 1.0)
STOCK_WEIGHT_DIP=0.30
STOCK_WEIGHT_FORWARD_PE=0.30
STOCK_WEIGHT_52W_RANGE=0.15
STOCK_WEIGHT_ALLOCATION=0.25

ETF_WEIGHT_DIP=0.40
ETF_WEIGHT_TER=0.20
ETF_WEIGHT_ALLOCATION=0.40
```

---

## CLI Reference & Usage

The application is controlled via a rich Typer CLI interface defined in `main.py` and GNU Make shortcuts.

### Portfolio Monitoring & Decision Execution

```bash
# Full Rebalancing Decision Pipeline (Quantitative + Gemini AI Batch Analysis)
make decision

# Run decision pipeline directly with verbose factor score breakdown
python main.py decision --verbose

# Run decision pipeline in quantitative-only mode (bypassing AI)
python main.py decision --skip-ai

# Calculate and display current portfolio valuation and asset distribution
python main.py get-snapshot

# Save timestamped snapshot to SQLite and trigger Cloud SSoT backup
python main.py save-snapshot

# Analyze consolidated portfolio sector and country exposure across active ETFs
python main.py analyze-exposure

# Qualitative CLI asset metric evaluator
python -m cli.recommend analyze-quality
```

### Asset Inspection & Data Sync

```bash
# Inspect composition, TER, top holdings, and breakdowns for an ETF
python main.py etf-details IE00B4L5Y983

# Inspect fundamental metrics (P/E, Market Cap, Debt/Equity) for a stock
python main.py stock-details AAPL

# Force manual pull of configuration and database files from Google Drive
python main.py pull-config

# Force manual push of local configuration files to Google Drive
python main.py push-config

# Synchronize live fundamental snapshots (stocks and ETFs) into SQLite history
python main.py sync-fundamentals
```

---

## Quality Gates & Testing Suite

The project enforces strict code quality standards, verified through automated GitHub Actions CI pipelines (`ci.yml`).  

Run the complete quality check suite locally using GNU Make:  

```bash
make quality
```

The quality suite executes:
- **Black**: Code formatting verification (`black --check`).
- **Ruff**: Fast Python linting and import sorting (`ruff check`).
- **Mypy**: Strict static type checking across all modules (`mypy`).
- **Bandit**: Security vulnerability scanning (`bandit`).
- **Pip-Audit**: Known dependency vulnerability auditing (`pip-audit`).
- **Pytest**: Unit test execution with rigorous branch coverage reporting (`pytest --cov=src`).  

---

## License

Distributed under the MIT License.

Developed and maintained by **João Pedro** ([@JoPedro15](https://github.com/JoPedro15)).

> *Fueled by Espresso, CrossFit WODs, and powered by Gemini AI collaboration.* ☕🏋️‍♂️🤖