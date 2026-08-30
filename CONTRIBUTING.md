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

## 3. Code Licensing & Intellectual Property
By submitting a Pull Request or contributing code to this repository, you agree that all your contributions will be licensed under the project's existing [LICENSE](LICENSE) (MIT License), and you warrant that you hold the necessary rights to submit the code free of encumbrances or third-party IP breaches.