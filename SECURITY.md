# Security

This document outlines the security measures implemented in the Confluence Summarizer application. The project takes a "Security First" approach to ensure safe deployment and operation.

## 1. Secrets Management
- All secrets and environment variables are excluded from version control via `.gitignore` to prevent accidental exposure (e.g., `.env`, `.pem`, `secrets/`).
- API keys, such as `APP_API_KEY`, are strictly required for production use and do not have an insecure fallback default in the main configuration schema.

## 2. Dependency Management
- **Automated Updates:** The project is configured with `renovate.json` to automatically track and update dependencies via pull requests.
- **Vulnerability Scanning:** The CI pipeline includes `pip-audit` to scan for known vulnerabilities in Python dependencies before any code is merged.

## 3. Code Security
- **API Authentication:** All FastAPI endpoints require an API Key provided in the `X-API-Key` header, validating against the configured `APP_API_KEY`.
- **CORS:** Cross-Origin Resource Sharing is controlled using FastAPI's `CORSMiddleware`. Allowed origins must be configured via the `ALLOWED_ORIGINS` environment variable.
- **Security Headers:** HTTP security headers are enforced across all responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## 4. CI/CD Security
- **Least-Privilege:** GitHub Actions workflows are configured with minimum required permissions (e.g., `permissions: contents: read`).
- **SAST Scanning:** Bandit is integrated into the testing pipeline to perform Static Application Security Testing on the source code to catch common security issues.

## Reporting a Vulnerability
If you discover a security vulnerability within this project, please open an issue or contact the repository maintainers directly.
