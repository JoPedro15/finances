# Security Policy

## Supported Versions

The following versions of **Finances Portfolio Tracker & Opportunity Engine** are currently supported with security updates:

| Version | Supported          |
| :------ | :----------------- |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, credential leak, or policy flaw within this repository:

1. **Do NOT create a public GitHub issue.**
2. Send a private security report directly to **João Pedro** ([@JoPedro15](https://github.com/JoPedro15)).
3. Provide detailed steps to reproduce the vulnerability, affected components, and potential impact.

### Expected Response Timeline
* **Initial Acknowledgment:** Within 48 hours.
* **Triage & Status Update:** Within 5 business days.
* **Fix & Patch Release:** Targeted within 14 business days depending on severity.

## Built-in Security Controls

This repository enforces automated Static Application Security Testing (SAST) and dependency vulnerability audits:

* **SAST Analysis:** Automated static code scans using `bandit` (`make security-check`).
* **Dependency Auditing:** Automated checks against known CVE databases using `pip-audit`.
* **Secrets Protection:** Environment variables (`.env`) and GCP OAuth tokens (`secrets/credentials.json`, `secrets/token.json`) are strictly excluded from source control via `.gitignore`.
## ⚠️ User Responsibility
**Security of Credentials:** You are solely responsible for the protection of your `GEMINI_API_KEY`, Google Cloud credentials, and Discord Webhooks. The author is NOT responsible for any financial loss or unauthorized access resulting from leaked secrets or improper server configuration.
