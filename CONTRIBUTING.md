# Contributing to EX-ACT

Thank you for your interest in contributing to EX-ACT (Environmental eXternalities ACcounting Tool). This project is maintained by the Agrifood Economics and Policy Division (ESA) of the Food and Agriculture Organization of the United Nations (FAO), in collaboration with the CSI Information Office.

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Ways to Contribute

- **Bug reports** — open a GitHub issue with reproduction steps, expected vs. actual behavior, and environment details.
- **Feature requests** — open a GitHub issue describing the use case and desired behavior before starting implementation.
- **Pull requests** — see the workflow below.
- **Documentation** — fixes and improvements to `README.md`, `docs/`, and inline docstrings are always welcome.
- **Security issues** — see [SECURITY.md](./SECURITY.md). Do **not** open a public issue for security vulnerabilities.

## Development Workflow

1. **Fork & clone** the repository.
2. **Create a feature branch** from `develop`: `git checkout -b feature/<short-name>`.
3. **Set up the local environment** per the [README](./README.md) Quick Start. Copy `djangoexact/.env.example` to `.env` and fill in the required variables — never commit real secrets.
4. **Write tests** for new behavior and run `pytest` locally.
5. **Run the linters** and security scans:
   ```bash
   pip install bandit pip-audit
   bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules
   pip-audit -r djangoexact/requirements.txt
   ```
6. **Commit** using clear, conventional messages (e.g., `fix: correct emission factor for livestock module`).
7. **Open a pull request** against `develop`. Fill in the PR template describing the change, test coverage, and any migration notes.

## Licensing of Contributions

By submitting a pull request, you agree that your contribution will be licensed under the [GNU Affero General Public License v3.0 or later](./LICENSE), the same license that covers the project.

Please confirm that:

- You are the original author of the contribution, or have permission from the rights holder.
- Your contribution does not introduce third-party code under a license incompatible with AGPL-3.0-or-later (e.g., proprietary, SSPL, BUSL, Commons Clause).

## Code Style

- **Python**: PEP 8 with a 120-character line limit; prefer type hints; write docstrings for public functions and classes.
- **JavaScript / TypeScript**: follow the project's Prettier and ESLint configuration.
- **Commits**: one logical change per commit; avoid bundling unrelated refactors.

## Questions

Reach out to the maintainers at **exact@fao.org** or open a discussion in the repository.
