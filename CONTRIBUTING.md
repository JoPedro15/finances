# Contributing Guidelines

Thank you for reviewing or contributing to this project!

## 1. Quality Gates
All contributions must pass local quality checks before opening a Pull Request:

* **Format & Lint:** Code must be formatted with `black` and pass `ruff` check (`make format` / `make lint`).
* **Type Safety:** Strict type annotations are required across all variables and functions (`mypy`).
* **Security:** SAST analysis (`bandit`) and dependency audit (`pip-audit`) must pass without high-severity issues (`make security-check`).
* **Tests:** Existing unit tests must pass with maintained coverage (`make test`).

## 2. Sensitive Data & Secrets Policy
* **Never Commit Credentials:** Never hardcode or commit API keys (`GEMINI_API_KEY`), GCP OAuth tokens (`secrets/credentials.json`), or database snapshots (`finances.db`).
* **Use Mock Data in Tests:** Ensure unit tests use static mock payloads instead of hitting live external endpoints.
* **Privacy:** Do not include real financial data in PR descriptions or screenshots.

## 3. Code Licensing & Intellectual Property
By submitting a Pull Request or contributing code to this repository, you agree that:
1. Your contribution is licensed under the **MIT License**.
2. You grant the project maintainer a perpetual, irrevocable license to use, modify, and distribute your code.
3. You warrant that you hold the necessary rights to submit the code free of encumbrances or third-party IP breaches.

## 4. Scraping Compliance
Contributors must ensure that any new data extraction logic (scrapers) is designed to respect the `robots.txt` and Terms of Service of target websites. Maintainers assume no responsibility for ToS violations by third-party contributors.
