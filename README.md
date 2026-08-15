# Finances Portfolio Tracker

A simple command-line tool to track and analyze personal investment portfolios.

## Features

-   Track stocks and ETFs from your portfolio defined in `data/portfolio.json`.
-   Fetch real-time market data using the Yahoo Finance API.
-   Record historical snapshots of your portfolio's value in `data/history.json`.
-   Analyze overall performance against acquisition costs.

## Setup

1.  **Prerequisites**: Ensure you have Python 3 installed on your system.
2.  **Install Dependencies**: Run the following command to install the required libraries from `requirements.txt`.
    ```sh
    make install
    ```

## Usage

This project uses a `Makefile` to simplify common operations. All commands are run from your terminal in the project's root directory.

| Command            | Description                                                                                                                               |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `make get-snapshot`  | Calculates and displays the current portfolio value without saving it. Ideal for a quick check.                                           |
| `make save-snapshot` | Calculates the current portfolio value and saves a timestamped snapshot to `data/history.json`. This records the portfolio's evolution. |
| `make analyze`       | Analyzes performance by comparing acquisition costs with the latest recorded value, showing gain/loss for each asset and the total ROI. |
| `make help`          | Displays a list of all available commands.                                                                                                |

