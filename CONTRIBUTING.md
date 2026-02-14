# Contributing to ConfluenceSummarizer

We love your input! We want to make contributing to ConfluenceSummarizer as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## Development Process

We use `uv` for dependency management and `GitHub Actions` for CI.

1.  **Fork the repo** and create your branch from `main`.
2.  **Install dependencies**:
    ```bash
    uv sync --all-extras --dev
    ```
3.  **Run checks** before committing:
    ```bash
    uv run flake8 src tests
    uv run pyright src
    uv run pytest
    ```
4.  **Submit a Pull Request**.

## Pull Request Guidelines

-   **Test Coverage**: Ensure 100% test coverage for new code.
-   **Type Hints**: Use strict type hints (checked by `pyright`).
-   **Style**: Follow Google-style docstrings and standard Python formatting.
-   **Commit Messages**: Use descriptive messages.

## Issues

We use GitHub issues to track public bugs. Report a bug by opening a new issue; it's that easy!
