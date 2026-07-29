# The EX-ACT App Codebase

> The official codebase for FAO's **Environmental eXternalities ACcounting Tool (EX-ACT)** online application.

[![License: AGPL v3+](https://img.shields.io/badge/License-AGPL_v3%2B-blue.svg)](./LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-092E20.svg)](https://www.djangoproject.com/)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-purple.svg)](./CODE_OF_CONDUCT.md)

This repository contains the source code for the EX-ACT web application, an open-access tool designed to evaluate environmental externalities of agrifood system interventions, with current coverage focused on greenhouse-gas (GHG) emissions and removals. The code supports computation of GHG emissions from agrifood interventions and covers carbon dioxide, methane, nitrous oxide, and refrigerants.

Emission factors and coefficients used in EX-ACT are primarily sourced from the **IPCC Guidelines for National Greenhouse Gas Inventories** (2006, 2014 refinement, and 2019 refinement).

EX-ACT is developed by the **Agrifood Economics and Policy Division (ESA)** of the **Food and Agriculture Organization of the United Nations (FAO)**, in collaboration with the **CSI Information Office**. The hosted version is available at **[exact.apps.fao.org](https://exact.apps.fao.org/)**.

Copyright (C) 2023-2026 Food and Agriculture Organization of the United Nations (FAO).
Licensed under the [GNU Affero General Public License v3.0 or later](./LICENSE).

---

## Table of Contents

- [Purpose](#purpose)
- [What you can do with EX-ACT](#what-you-can-do-with-ex-act)
- [Tool coverage (GHG assessments)](#tool-coverage-ghg-assessments)
- [Tech stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Reference data and fixtures](#reference-data-and-fixtures)
- [API documentation](#api-documentation)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Acknowledgement](#acknowledgement)
- [Help and contact](#help-and-contact)
- [Security](#security)
- [License](#license)

---

## Purpose

The EX-ACT app codebase supports the environmental assessment of agrifood system interventions by enabling evidence-based decision-making through a transparent and reproducible framework. By making the application code available, the project aims to facilitate peer review, reuse, and collaboration across institutions and practitioners engaged in climate-mitigation appraisal and reporting for agrifood investments.

## What you can do with EX-ACT

The EX-ACT online application allows users to:

- **Estimate** CO₂, CH₄, and N₂O emissions and removals from land-based and agricultural production activities, including land-use change, land and soil management, biomass and soil carbon-stock changes, crop and grassland management practices, fertilizer and residue management, rice cultivation, and other field-level activities.
- **Estimate** GHG emissions from livestock activities through dedicated modules that account for emissions from enteric fermentation, manure management, and feed-production inputs, using activity data, herd or production parameters, and emission coefficients.
- **Account** for emissions from non-land-based and downstream value-chain activities, including energy use and emissions from processing, storage, refrigeration, transport, packaging, and other post-farm operations relevant to agrifood systems.
- **Apply** IPCC Tier 1 default coefficients or incorporate Tier 2 location-specific parameters where available, while maintaining internal consistency across modules and scenarios.
- **Aggregate** GHG emissions and removals across activities and modules to compute net project-level carbon balances expressed in CO₂-equivalent terms over the assessment period.
- **Disaggregate** results by greenhouse gas (CO₂, CH₄, N₂O), activity, scenario (baseline vs. intervention), land-use and livestock category, or value-chain component.
- **Track** changes in emissions and removals over time by defining multiple implementation phases within activities, allowing the representation of gradual adoption or phased interventions.

## Tool coverage (GHG assessments)

The current release covers GHG emissions from the following activities:

- **Land-use change (LUC).** Estimates CO₂ and N₂O fluxes from conversions between land-use categories by accounting for changes in above- and below-ground biomass, dead organic matter, and soil organic carbon stocks.
- **Annual cropland management.** Estimates CO₂ and N₂O emissions related to soil organic carbon stock changes driven by tillage and management practices, as well as CH₄ and N₂O emissions linked to residue management.
- **Rice cultivation.** Estimates CH₄ emissions from flooded rice systems as a function of water management, organic amendments, and cultivation period, and N₂O emissions associated with residue management.
- **Perennial crops and agroforestry systems.** Estimates CO₂ and N₂O fluxes from biomass growth and soil organic carbon dynamics associated with perennial cropping and agroforestry management.
- **Grassland and pasture management.** Estimates CO₂ emissions and removals from changes in soil organic carbon stocks and CH₄ and N₂O fluxes from residue burning.
- **Forest management.** Estimates CO₂ emissions and removals from afforestation, reforestation, deforestation, and forest management through changes in forest biomass and soil carbon stocks. Also estimates CH₄ and N₂O fluxes from forest biomass burning.
- **Livestock production.** Estimates CH₄ emissions from enteric fermentation and manure management systems, and direct and indirect N₂O emissions from manure management.
- **Fisheries.** Estimates CO₂-eq emissions from fuel and energy use and, where applicable, refrigerant emissions.
- **Inland wetlands.** Estimates CO₂, CO, CH₄, and N₂O fluxes associated with land-use change and management of inland wetlands, including drainage and rewetting.
- **Coastal wetlands.** Estimates CO₂ and CH₄ fluxes from management of coastal wetland ecosystems, including soil, biomass, drainage, and rewetting.
- **Water bodies.** Estimates CH₄ emissions from management of inland and coastal water bodies based on trophic status and management practices, reflecting GHG fluxes associated with organic-matter dynamics in aquatic systems.
- **Aquaculture.** Estimates N₂O emissions from aquaculture-related activities through fish excreta.
- **Agrochemical and input use.** Estimates CO₂ emissions from the production and transport of agricultural inputs and N₂O and CO₂-eq emissions resulting from application to soils.
- **Energy use and irrigation.** Estimates CO₂, CH₄, and N₂O emissions from fuel combustion and electricity use for irrigation and mechanized operations.
- **Transport, processing, storage, and packaging.** Estimates CO₂, CH₄, N₂O, and CO₂-eq emissions from energy use and materials in post-harvest transport, processing, storage, refrigeration, drying, and packaging.

For the methodological background, see the bundled [EX-ACT user guide (PDF)](./EXACT_guide.pdf) and the in-app docs at `/api/docs/` once the server is running.

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web framework | Django 5.2, Django REST Framework 3.16 |
| Auth | SimpleJWT, Firebase Admin SDK |
| API docs | drf-spectacular, drf-yasg |
| Frontend assets | Webpack 5, Tailwind CSS 3, React (via `@tanstack/react-store`) |
| Reports | WeasyPrint |
| Database | PostgreSQL (production), SQLite (local minitool) |
| Deployment | Google App Engine and Cloud Run, via Bitbucket Pipelines |

Under the hood, the application combines:

- **IPCC default factors** for AFOLU sectors, packaged as versioned reference data.
- **Calculator modules** mapped one-to-one onto the underlying Django models, so every number in the report can be traced back to its inputs.
- **A pure math layer** (`djangoexact/math_model/`) that is independent of Django and can be tested in isolation.

## Prerequisites

- **Python 3.11** (use exactly 3.11; newer minor versions are not yet supported in production)
- **pip** and **virtualenv** (`pip install virtualenv`)
- **Node.js and npm** for frontend asset builds
- **Git**
- **WeasyPrint system libraries** (Pango, Cairo, GDK-PixBuf). See the [setup guide](./docs/setup-guide.md) for OS-specific instructions.
- *(Optional)* **Google Cloud SDK** and **Cloud SQL Proxy** if you need to connect to a shared database environment.

The full developer setup, including VS Code debugger configuration and Cloud SQL Proxy steps, lives in [`docs/setup-guide.md`](./docs/setup-guide.md). The Quick Start below covers only the local-only path.

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/un-fao/exact-django-webapp.git
cd exact-django-webapp
```

### 2. Create and activate a virtual environment

```bash
virtualenv env --python=python3.11
```

```bash
# macOS / Linux
source env/bin/activate

# Windows (PowerShell)
.\env\Scripts\Activate.ps1

# Windows (Git Bash or cmd)
source env/Scripts/activate
```

### 3. Install Python dependencies

```bash
pip install -r djangoexact/requirements.txt
```

### 4. Install frontend dependencies and build assets

```bash
cd djangoexact
npm install
npm run build
```

### 5. Configure your environment

Copy the example file and fill in the required values:

```bash
cp djangoexact/.env.example djangoexact/.env
```

See [Configuration](#configuration) for the variables you need to set. **Never commit real secrets.**

### 6. Initialize the database

```bash
# from djangoexact/
python manage.py migrate
python manage.py createsuperuser
```

### 7. Load reference data

```bash
python manage.py load_reference_data --app=all
```

### 8. Run the development server

```bash
python manage.py runserver
```

The API is now available at `http://localhost:8000/api/` and the admin at `http://localhost:8000/admin/`.

## Configuration

All settings are driven by `.env` files in `djangoexact/`. The expected variables and their defaults are documented in `djangoexact/.env.example`. Common keys include:

| Variable | Purpose |
|---|---|
| `APP_MODE` | Selects the active env profile: `development`, `review`, or `production`. |
| `SECRET_KEY` | Django secret key. Required. |
| `DATABASE_URL` | PostgreSQL DSN. SQLite is used as a fallback for the minitool. |
| `FIREBASE_*` | Firebase Admin credentials for authenticated endpoints. |
| `ALLOWED_HOSTS` | Comma-separated host list. |
| `CORS_*` | Cross-origin policy for the SPA frontend. |

Production secrets are managed in Google Cloud Secret Manager and are not stored in the repository. Local credentials must be obtained from a project maintainer; see [`docs/setup-guide.md`](./docs/setup-guide.md).

## Reference data and fixtures

To bootstrap a fresh database with all reference data (IPCC tables, types, countries, regions, and so on):

```bash
python manage.py load_reference_data --app=all
```

The full dump/load workflow, PK-stability guardrails, determinism guarantees, and instructions for adding a new reference model are documented in [`djangoexact/docs/guides/fixtures-guide.md`](./djangoexact/docs/guides/fixtures-guide.md).

## API documentation

Once the server is running:

- **Built-in API docs**: <http://localhost:8000/api/docs/>
- **Swagger UI**: <http://localhost:8000/api/swagger/>
- **ReDoc**: <http://localhost:8000/api/redoc/>
- **OpenAPI schema**: downloadable in JSON and YAML formats from the docs pages above.

### Postman

A ready-to-import collection ships with the repository as `EX-ACT.postman_collection.json`. You can also open it in Postman with one click:

[![Run in Postman](https://run.pstmn.io/button.svg)](https://app.getpostman.com/run-collection/7002893-9d88940d-a037-477a-b287-d42e01c25749?action=collection%2Ffork&collection-url=entityId%3D7002893-9d88940d-a037-477a-b287-d42e01c25749%26entityType%3Dcollection%26workspaceId%3D7e75d44c-4b11-4375-afea-b500866e6198)

## Testing

The test suite uses `pytest`. From `djangoexact/`:

```bash
pytest                    # run everything
pytest api/tests/         # run a specific app's tests
pytest -k livestock       # run tests matching a keyword
pytest -x --ff            # stop on first failure, run failures first next time
```

Security and dependency scans:

```bash
pip install bandit pip-audit
bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules
pip-audit -r djangoexact/requirements.txt
```

## Project layout

```
exact-django-webapp/
├── djangoexact/                  # Django project root (manage.py lives here)
│   ├── djangoexact/              # Settings, URLs, ASGI/WSGI entrypoints
│   ├── api/                      # Core REST API: projects, scenarios, calculators
│   │   ├── calculators.py        # One calculator class per Django model
│   │   ├── services/             # Domain services
│   │   ├── reports/              # PDF report generation
│   │   └── tests/                # API test suite
│   ├── math_model/               # Pure math, framework-agnostic
│   │   └── no_time_dependency_final/  # Emission factor calculations
│   ├── ipcc/                     # IPCC reference data app
│   ├── accounts/                 # Users, JWT + Firebase auth, permissions
│   ├── blog/                     # In-app news and announcements
│   ├── minitool/                 # Lightweight standalone calculator
│   ├── static/, media/, locale/  # Assets, uploads, translations
│   └── requirements.txt
├── deploy/                       # Deployment helpers
├── gcp-deployment/               # Google Cloud build configuration
├── docs/                         # Developer documentation and design plans
│   ├── setup-guide.md
│   ├── faostat-integration.md
│   └── plans/
├── EXACT_guide.pdf               # Methodological user guide
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE
```

## Deployment

EX-ACT is deployed on **Google Cloud Platform**:

- The web API runs on **App Engine Standard** (`djangoexact/app.yaml`).
- Background jobs run on **Cloud Run**.
- The database is **Cloud SQL for PostgreSQL**.
- CI/CD is orchestrated through **Bitbucket Pipelines** (see `bitbucket-pipelines.yml`).

Self-hosting is supported. The application is a standard Django project, so any platform that can run Django and serve static assets (Heroku, Render, Fly.io, a Docker host) will work, provided you supply a PostgreSQL database and the WeasyPrint system libraries.

## Contributing

Contributions are welcome and very much appreciated. Please read:

- [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the development workflow, code style, and PR process.
- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) for community standards.

In short:

1. Fork the repository and create a feature branch from `develop`.
2. Write tests for new behavior and run `pytest` locally.
3. Run `bandit` and `pip-audit` before opening a PR.
4. Use conventional commit messages (e.g., `fix: correct emission factor for livestock module`).
5. Open a pull request against `develop` and fill in the PR template.

By submitting a contribution, you agree to license it under AGPL-3.0-or-later.

## Acknowledgement

The current version of EX-ACT has been developed with contributions of the **International Fund for Agricultural Development (IFAD)**.

## Help and contact

Users are encouraged to share feedback and to contact the EX-ACT team for documentation, methodological questions, or technical support:

- **Email**: [ex-act@fao.org](mailto:ex-act@fao.org)
- **Hosted version**: <https://exact.apps.fao.org/>
- **Bug reports and feature requests**: open an issue on GitHub
- **Security vulnerabilities**: see [`SECURITY.md`](./SECURITY.md)

## Security

If you believe you have found a security vulnerability, **please do not open a public GitHub issue.** Report it privately by emailing **ex-act@fao.org** with the subject line `[SECURITY] <short description>`. Full details, including expected response times and safe-harbor language, are in [`SECURITY.md`](./SECURITY.md).

## License

This code is licensed under the **GNU Affero General Public License v3.0 or later** ([`AGPL-3.0-or-later`](./LICENSE)), which permits free use, modification, and sharing.

Under AGPL-3.0, any modifications to the code must be made publicly available, for example by creating a new branch on GitHub. The software cannot be relicensed under more restrictive terms without adhering to the AGPL-3.0 guidelines. Developers may anonymize or remove any sensitive or identifiable data (customizations) before resubmitting code.

The AGPL is a copyleft license: if you modify EX-ACT and run the modified version as a network service, you must make the source code of your version available to its users under the same license. See [`LICENSE`](./LICENSE) for the full text.

Copyright (C) 2023-2026 Food and Agriculture Organization of the United Nations (FAO).
