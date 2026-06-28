# Contributing to AI SRE Copilot

Thank you for your interest in contributing to AI SRE Copilot! We welcome contributions to help improve this autonomous incident response platform.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs
* Check the existing issues to ensure the bug hasn't already been reported.
* Open a new issue using our **Bug Report Template**.
* Provide a clear description, reproduction steps, and logs.

### Proposing Features
* Open a new issue using our **Feature Request Template**.
* Describe the feature, why it is useful, and potential implementation ideas.

### Submitting Pull Requests
1. Fork the repository and create a new branch from `main`.
2. Add unit or integration tests for any new features or bug fixes.
3. Verify that all tests pass locally by running `uv run pytest`.
4. Ensure your code passes all lint and format checks by running `uv run ruff check` and `uv run ruff format --check`.
5. Open a Pull Request referencing the related issue and fill out the PR template.

## Development Setup

See the main [README.md](README.md) for local development and setup instructions.
We use `uv` for dependency management:
- Install development dependencies: `uv sync`
- Format code: `uv run ruff format`
- Check lint rules: `uv run ruff check`

Thank you for contributing!
