# EX-ACT Django Webapp — Developer Setup Guide

This guide walks you through setting up the EX-ACT Django web application from scratch on your local machine. It covers everything from installing Python and VS Code to debugging emission calculations.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
   - [Install Python 3.11](#11-install-python-311)
   - [Install VS Code](#12-install-vs-code)
   - [Install VS Code Extensions](#13-install-vs-code-extensions)
   - [Install Google Cloud SQL Proxy](#14-install-google-cloud-sql-proxy)
2. [Project Setup](#2-project-setup)
   - [Clone the Repository](#21-clone-the-repository)
   - [Create a Virtual Environment](#22-create-a-virtual-environment)
   - [Install Dependencies](#23-install-dependencies)
3. [Environment Configuration](#3-environment-configuration)
   - [How Environment Files Work](#31-how-environment-files-work)
   - [Creating Your .env Files](#32-creating-your-env-files)
   - [Switching Between Environments](#33-switching-between-environments)
4. [Database Access with Cloud SQL Proxy](#4-database-access-with-cloud-sql-proxy)
   - [Authenticating with GCloud](#41-authenticating-with-gcloud)
   - [Available Database Environments](#42-available-database-environments)
   - [Running the Proxy](#43-running-the-proxy)
5. [Running the Application](#5-running-the-application)
6. [Debugging in VS Code](#6-debugging-in-vs-code)
   - [Setting Up the Debugger](#61-setting-up-the-debugger)
   - [Using Breakpoints](#62-using-breakpoints)
   - [Debugging the Calculators & Math Model](#63-debugging-the-calculators--math-model)
   - [Using the Debug Variables Panel](#64-using-the-debug-variables-panel)
   - [Practical Debugging Walkthrough](#65-practical-debugging-walkthrough)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

### 1.1 Install Python 3.11

This project requires **Python 3.11.x**. Other versions may cause compatibility issues with dependencies.

**macOS (using Homebrew):**

```bash
brew install python@3.11
```

Verify the installation:

```bash
python3.11 --version
```

You should see `Python 3.11.x`.

**Windows:**

1. Download the Python 3.11.x installer from [python.org](https://www.python.org/downloads/)
2. Run the installer — **check "Add python.exe to PATH"** before clicking Install
3. Open a new terminal and verify:

```bash
python --version
```

> <!-- IMAGE: Screenshot of the Python installer with "Add to PATH" checkbox highlighted -->

### 1.2 Install VS Code

1. Download VS Code from [code.visualstudio.com](https://code.visualstudio.com/)
2. Run the installer for your platform
3. Launch VS Code

> <!-- IMAGE: VS Code welcome screen after first launch -->

### 1.3 Install VS Code Extensions

Open VS Code, go to the Extensions sidebar (`Cmd+Shift+X` on macOS, `Ctrl+Shift+X` on Windows), and install the following:

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| **Python** | Microsoft | Python language support, IntelliSense, linting |
| **Pylance** | Microsoft | Fast, feature-rich Python language server |
| **Django** | Baptiste Darthenay | Django template syntax highlighting |
| **Python Debugger** | Microsoft | Breakpoints, variable inspection, step-through |
| **GitLens** | GitKraken | Git blame, history, and navigation |
| **Thunder Client** | Ranga Vadhineni | REST API testing (alternative to Postman) |
| **SQLTools** | Matheus Teixeira | Database browser and query runner |
| **SQLTools PostgreSQL** | Matheus Teixeira | PostgreSQL driver for SQLTools |

You can also install them from the terminal:

```bash
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension batisteo.vscode-django
code --install-extension ms-python.debugpy
code --install-extension eamodio.gitlens
code --install-extension rangav.vscode-thunder-client
code --install-extension mtxr.sqltools
code --install-extension mtxr.sqltools-driver-pg
```

> <!-- IMAGE: VS Code extensions sidebar with the above extensions installed -->

### 1.4 Install Google Cloud SQL Proxy

The Cloud SQL Proxy lets you connect to remote GCP PostgreSQL databases as if they were running locally.

**macOS (Apple Silicon):**

```bash
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.darwin.arm64
chmod +x cloud-sql-proxy
```

**macOS (Intel):**

```bash
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.darwin.amd64
chmod +x cloud-sql-proxy
```

**Windows:**

Download from the [Cloud SQL Proxy releases page](https://cloud.google.com/sql/docs/postgres/sql-proxy) and place it in a directory on your PATH.

Move the binary somewhere accessible (e.g. your home `~/Developer/` directory or `/usr/local/bin/`):

```bash
mv cloud-sql-proxy ~/Developer/cloud-sql-proxy
```

Install the Google Cloud CLI if you don't have it:

**macOS:**

```bash
brew install google-cloud-sdk
```

**Windows:**

Download and run the installer from the [Google Cloud CLI page](https://cloud.google.com/sdk/docs/install#windows).

---

## 2. Project Setup

### 2.1 Clone the Repository

```bash
git clone <repository-url>
cd exact-django-webapp
```

### 2.2 Create a Virtual Environment

From the project root:

```bash
python3.11 -m venv venv
```

Activate it:

**macOS / Linux:**

```bash
source venv/bin/activate
```

**Windows:**

```bash
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

> <!-- IMAGE: Terminal showing (venv) prefix after activation -->

### 2.3 Install Dependencies

```bash
cd djangoexact
pip install -r requirements.txt
```

This installs Django 4.2, DRF, numpy, pandas, and all other project dependencies. The installation may take a few minutes.

If you encounter issues with `psycopg2-binary`, make sure you have PostgreSQL client libraries:

```bash
# macOS
brew install libpq

# or if that doesn't help
pip install psycopg2-binary --no-cache-dir
```

---

## 3. Environment Configuration

### 3.1 How Environment Files Work

The application uses `python-dotenv` with a multi-layered environment loading strategy defined in `djangoexact/djangoexact/settings.py`:

1. A base `.env` file is loaded first (general defaults)
2. If the `APP_MODE` environment variable is set, it then loads `.env.{APP_MODE}` which overrides the base values

The environment files live at:

```
djangoexact/djangoexact/.env              ← base (always loaded)
djangoexact/djangoexact/.env.development  ← local development
djangoexact/djangoexact/.env.review       ← review environment
djangoexact/djangoexact/.env.production   ← production environment
djangoexact/djangoexact/.env.test         ← test environment
```

These files are **gitignored** and contain secrets (database credentials, Firebase keys, etc.), so they are never committed to the repository.

### 3.2 Getting Your .env Files

**Ask a team member** for the pre-configured `.env` files. You will receive files like `.env.development`, `.env.review`, etc. Place them at:

```
djangoexact/djangoexact/.env.development
djangoexact/djangoexact/.env.review
djangoexact/djangoexact/.env.production
```

That's it — no manual editing needed. The files come ready to use.

> <!-- IMAGE: Finder/Explorer showing the .env files placed in the djangoexact/djangoexact/ directory -->

<details>
<summary><strong>Advanced: creating .env files manually</strong></summary>

If you need to create a `.env` file from scratch (rare), here is the expected structure:

```env
SECRET_KEY=your-secret-key
DB_ENGINE=django.db.backends.postgresql
DB_HOST=127.0.0.1
DB_USER=your-db-username
DB_PASSWORD=your-db-password
DB_NAME=your-db-name
DB_PORT=5432

EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
SMTP_USER_EMAIL=your-email
SMTP_USER_PASSWORD=your-email-password

FIREBASE_API_KEY=your-firebase-key
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your-sender-id
FIREBASE_APP_ID=your-app-id
FIREBASE_MEASUREMENT_ID=your-measurement-id
FIREBASE_SERVICE_ACCOUNT=base64-encoded-service-account-json

STORAGE_BUCKET=your-storage-bucket
```

The `FIREBASE_SERVICE_ACCOUNT` value must be the base64-encoded content of your Firebase service account JSON file:

```bash
base64 -i path/to/service-account.json
```

</details>

### 3.3 Switching Between Environments

Set the `APP_MODE` environment variable before running the server:

**Connect to dev database:**

```bash
APP_MODE=development python manage.py runserver
```

**Connect to review database:**

```bash
APP_MODE=review python manage.py runserver
```

**Connect to production database (read-only operations only!):**

```bash
APP_MODE=production python manage.py runserver
```

You can also export `APP_MODE` for your terminal session:

```bash
export APP_MODE=development
python manage.py runserver
```

> <!-- IMAGE: Terminal output showing "Running in development mode" after server start -->

---

## 4. Database Access with Cloud SQL Proxy

The EX-ACT databases are hosted on Google Cloud SQL (PostgreSQL). To access them locally, you need to run the Cloud SQL Proxy, which creates a secure tunnel.

### 4.1 Authenticating with GCloud

Before using the proxy, authenticate with Google Cloud:

```bash
gcloud auth login
gcloud auth application-default login
```

This opens a browser window for authentication. Make sure you log in with your FAO Google account that has access to the GCP projects.

> <!-- IMAGE: Browser showing Google Cloud authentication prompt -->

### 4.2 Available Database Environments

| Environment | GCP Project | Instance Connection | Use Case |
|-------------|-------------|---------------------|----------|
| **Dev** | `fao-exact-dev` | `fao-exact-dev:europe-west1:fao-exact-dev-postgres` | Day-to-day development |
| **Review** | `fao-exact-review` | `fao-exact-review:europe-west1:fao-exact-review-postgres` | Testing before production |
| **Production** | `fao-exact` | `fao-exact:europe-west1:fao-exact-postgres` | Live data (be careful!) |

### 4.3 Running the Proxy

The proxy binds to `localhost:5432`, making the remote database appear as a local PostgreSQL instance.

**Dev environment:**

```bash
~/Developer/cloud-sql-proxy -p 5432 fao-exact-dev:europe-west1:fao-exact-dev-postgres
```

**Review environment:**

```bash
~/Developer/cloud-sql-proxy fao-exact-review:europe-west1:fao-exact-review-postgres --port=5432
```

**Production environment:**

```bash
~/Developer/cloud-sql-proxy -p 5432 fao-exact:europe-west1:fao-exact-postgres
```

> **Keep the proxy running** in a separate terminal tab/window. It must stay active while you work with the database.

> <!-- IMAGE: Terminal showing Cloud SQL Proxy output with "Ready for new connections" message -->

Once the proxy is running, your `.env` file's `DB_HOST=127.0.0.1` and `DB_PORT=5432` will route through the proxy to the remote database.

To verify the connection works:

```bash
APP_MODE=development python manage.py dbshell
```

This should drop you into a PostgreSQL shell connected to the remote database.

---

## 5. Running the Application

With the proxy running and your `.env` file configured:

```bash
cd djangoexact
APP_MODE=development python manage.py runserver
```

The server starts at `http://localhost:8000/`. Key URLs:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/admin/` | Django Admin panel |
| `http://localhost:8000/api/` | API root |
| `http://localhost:8000/api/docs/` | API documentation |
| `http://localhost:8000/api/swagger/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc documentation |

> <!-- IMAGE: Browser showing the Django admin login page -->

---

## 6. Debugging in VS Code

### 6.1 Setting Up the Debugger

Create the file `.vscode/launch.json` in the **project root** with this configuration:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Django: Dev",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/djangoexact/manage.py",
      "args": ["runserver", "--noreload"],
      "django": true,
      "env": {
        "APP_MODE": "development"
      },
      "justMyCode": false
    },
    {
      "name": "Django: Review",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/djangoexact/manage.py",
      "args": ["runserver", "--noreload"],
      "django": true,
      "env": {
        "APP_MODE": "review"
      },
      "justMyCode": false
    },
    {
      "name": "Django: Production (READ-ONLY)",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/djangoexact/manage.py",
      "args": ["runserver", "--noreload"],
      "django": true,
      "env": {
        "APP_MODE": "production"
      },
      "justMyCode": false
    }
  ]
}
```

Key settings explained:
- **`--noreload`**: Prevents Django's auto-reloader from interfering with the debugger. Without this, breakpoints may not work reliably.
- **`"django": true`**: Enables Django-specific debugging support (template debugging, etc.).
- **`"justMyCode": false`**: Allows stepping into library code and the math model modules, which is essential for debugging calculations.
- **`"env"`**: Sets the `APP_MODE` so the correct `.env.{mode}` file is loaded.

> <!-- IMAGE: VS Code launch.json file with the configurations above -->

### 6.2 Using Breakpoints

1. Open any Python file in VS Code
2. Click in the gutter (left of the line numbers) to place a red dot — that's a breakpoint
3. Start the debugger with `F5` (or click the green play button in the Run & Debug sidebar)
4. Trigger the code path (e.g. make an API request) — execution pauses at your breakpoint

> <!-- IMAGE: VS Code editor with a breakpoint set, showing the red dot in the gutter -->

**Breakpoint types:**

| Type | How to Set | Use Case |
|------|-----------|----------|
| **Line breakpoint** | Click the gutter | Pause at a specific line |
| **Conditional breakpoint** | Right-click gutter → "Add Conditional Breakpoint" | Pause only when a condition is true (e.g. `module_name == "AnnualCropland"`) |
| **Logpoint** | Right-click gutter → "Add Logpoint" | Log a message without pausing execution |
| **Exception breakpoint** | In the Breakpoints panel, check "Raised Exceptions" | Pause when any exception is thrown |

> <!-- IMAGE: Right-click menu showing conditional breakpoint option -->

### 6.3 Debugging the Calculators & Math Model

The EX-ACT calculation pipeline follows this flow:

```
API Request
  → View / ViewSet
    → Calculator (djangoexact/api/calculators.py)
      → Math Model (djangoexact/math_model/no_time_dependency_final/*.py)
        → Result / Inventory objects
```

#### The Calculators Layer (`djangoexact/api/calculators.py`)

Each Django model has a corresponding calculator class (e.g. `AnnualCroplandCalculator`, `DeforestationCalculator`, `ForestManagementCalculator`). These calculators:

1. Fetch input data from Django model instances
2. Look up IPCC default values
3. Build keyword-argument dictionaries (`self.inputs_w`, `self.inputs_wo`)
4. Instantiate the math model class (e.g. `MathAnnualCropland(**self.inputs_w)`)
5. Call `calculate_emissions()` on the math model
6. Return the `MathResult` object

**Good breakpoint locations in `calculators.py`:**

- Inside any calculator's `calculate()` method — right before the math model is instantiated
- On the line where `calculate_emissions()` is called
- On the `return` statement to inspect final results

#### The Math Model Layer (`djangoexact/math_model/no_time_dependency_final/`)

The math model files contain the actual emission calculation logic:

| File | Class | What It Calculates |
|------|-------|--------------------|
| `annuals.py` | `AnnualCropland` | Annual cropland emissions (SOC, biomass, N₂O) |
| `defo.py` | `Defo` | Deforestation emissions |
| `forest_management.py` | `ForestManagement` | Forest management (AGB/BGB matrices) |
| `perennial_cropping.py` | `PerennialTreeCrop` | Perennial/tree crop emissions |
| `flooded_rice.py` | `FloodedRice` | Flooded rice methane emissions |
| `grassland_management.py` | `GrasslandManagement` | Grassland SOC and biomass changes |
| `coastal_wetlands.py` | `CoastalWetland` | Mangrove and tidal marsh emissions |
| `fisheries_and_aquaculture.py` | `Fishery`, `CoastalAquaculture` | Fisheries fuel and aquaculture emissions |
| `inlands.py` | `AnnexedModule`, `PeatExtraction` | Organic soils, peat drainage/rewetting |
| `inputs.py` | `ElectricityConsumption`, `SolidAndLiquidFuelsConsumption`, etc. | Energy and input emissions |
| `livestock.py` | `Livestock` | Enteric fermentation, manure management |
| `value_chains.py` | Various | Storage, processing, packaging, transport |
| `waterbodies.py` | `Waterbodies` | Reservoir and waterbody emissions |

All math model classes inherit from `BaseModule` or `LandModule` (defined in `generalized_modules.py`) and share the same pattern:

- `__post_init__()` initializes `self.result` (a `MathResult`) and `self.inventory` (an `Inventory`)
- `calculate_emissions()` populates them

**Good breakpoint locations in math model files:**

- Inside `calculate_emissions()` methods — step through the calculation logic
- Inside `general_functions.py` helper functions like `compute_yearly_or_half_year_cumulative()`, `soil_emissions()`, `biomass_emissions()`

### 6.4 Using the Debug Variables Panel

When execution is paused at a breakpoint, the **Variables** panel (left sidebar in the Debug view) is your most powerful tool.

> <!-- IMAGE: VS Code Debug sidebar showing the Variables panel with Locals, self, and result objects expanded -->

#### Locals

Shows all variables in the current scope. For a calculator method, you'll see:

- `self` — the calculator instance
- `self.inputs_w` / `self.inputs_wo` — the dictionaries of inputs passed to the math model (inspect these to verify the right values are being sent)

#### Inspecting `self` on Math Model Objects

When paused inside a math model's `calculate_emissions()`:

- `self.result` — the `MathResult` object being built
  - `self.result.yearly_emissions_by_sector_by_gas` — list of `YearlyGasActivityEmissionSet` objects, each with:
    - `.year` — the year index
    - `.gas_type` — the greenhouse gas (`CO2`, `CH4`, `N2O`)
    - `.activity` — the activity type
    - `.emissions` — list of `Emission` objects with `.value`
- `self.inventory` — the `Inventory` object
  - `self.inventory.emissions_by_sector_by_gas` — list of `InventoryPerGasPerActivity` objects with `.gas_type`, `.value`, `.activity`

> <!-- IMAGE: Variables panel expanded showing self.result with yearly_emissions_by_sector_by_gas list -->

#### Watch Expressions

Add custom watch expressions in the **Watch** panel (click the `+` button):

Useful watches when debugging calculations:

```
self.result.yearly_emissions_by_sector_by_gas
len(self.result.yearly_emissions_by_sector_by_gas)
self.hectares_total
self.soc_start
self.soc_end
self.implementation_time
self.capitalization_time
```

> <!-- IMAGE: Watch panel with custom expressions added -->

#### Debug Console

The **Debug Console** (`Cmd+Shift+Y` / `Ctrl+Shift+Y`) lets you evaluate arbitrary Python expressions while paused:

```python
# Check the total emissions across all years for a specific gas
sum(e.value for yset in self.result.yearly_emissions_by_sector_by_gas
    for e in yset.emissions)

# Inspect a specific input dictionary
self.inputs_w.keys()

# Check what IPCC values were fetched
self.inputs_w.get('soc_reference')
```

> <!-- IMAGE: Debug Console with Python expressions being evaluated -->

### 6.5 Practical Debugging Walkthrough

Here's a step-by-step example of debugging an annual cropland calculation:

**1. Set breakpoints:**

- `calculators.py` — inside `AnnualCroplandCalculator.calculate()`, on the line that creates `MathAnnualCropland(**self.inputs_w)`
- `annuals.py` — inside `AnnualCropland.calculate_emissions()`, at the first line

**2. Start the debugger** (`F5`, select "Django: Dev")

**3. Trigger the calculation** by making an API request (via browser, Thunder Client, or Postman) that invokes the annual cropland calculation

**4. Execution pauses** at the first breakpoint in `calculators.py`:

- In the **Variables** panel, expand `self.inputs_w` to see all the keyword arguments
- Verify values like `hectares`, `implementation_years`, `soc_reference`, `flu`, `fmg`, `fi` are correct
- Check if any Tier 2 overrides are set (`*_tier_2` fields)

> <!-- IMAGE: Debugger paused in calculators.py with self.inputs_w expanded in Variables panel -->

**5. Press `F5` (Continue)** — execution moves to the breakpoint in `annuals.py`

**6. Step through** with `F10` (Step Over) or `F11` (Step Into):

- Watch `self.soc_start` and `self.soc_end` get calculated
- Step into `self.calculate_soc_som()` to see soil organic carbon computation
- Step into `general_functions.soil_emissions()` to see the yearly emission curves

> <!-- IMAGE: Stepping through annuals.py with F10, showing variables updating in real-time -->

**7. Check the result:**

- After `calculate_emissions()` completes, inspect `self.result` in the Variables panel
- Expand `yearly_emissions_by_sector_by_gas` to see per-year, per-gas emissions
- Check `self.inventory.emissions_by_sector_by_gas` for the aggregated totals

#### Debug Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Start / Continue |
| `F10` | Step Over (next line, skip function internals) |
| `F11` | Step Into (go inside a function call) |
| `Shift+F11` | Step Out (finish current function, return to caller) |
| `Shift+F5` | Stop debugging |
| `Cmd+Shift+F5` | Restart debugging |

> <!-- IMAGE: GIF showing full debug flow — setting breakpoint, hitting it, inspecting variables, stepping through -->

---

## 7. Troubleshooting

### "Firebase config not found" on startup

The Firebase service account is required even for local development. Make sure `FIREBASE_SERVICE_ACCOUNT` is set in your `.env` file and is valid base64.

```bash
# Test your base64 value
echo "your-base64-value" | base64 -d | python -m json.tool
```

### Cloud SQL Proxy: "connection refused"

- Make sure the proxy is **running** in a separate terminal
- Verify you're authenticated: `gcloud auth application-default login`
- Check that no other process is using port 5432: `lsof -i :5432`
- If PostgreSQL is installed locally and running, stop it or use a different port

### "No module named 'math_model'"

You need to run from the `djangoexact/` directory, where `math_model/` is a direct subdirectory:

```bash
cd djangoexact
python manage.py runserver
```

### Breakpoints not hitting

- Make sure you're using `--noreload` in the launch configuration (already included in the `launch.json` above)
- Verify the file you're setting breakpoints in is actually being executed (not a cached `.pyc` version)
- Try deleting all `__pycache__` directories:

```bash
find . -type d -name __pycache__ -exec rm -rf {} +
```

### Database migrations

If you get migration-related errors after pulling new changes:

```bash
APP_MODE=development python manage.py migrate
```

### WeasyPrint installation issues

WeasyPrint (used for PDF report generation) requires system-level libraries:

```bash
# macOS
brew install pango gdk-pixbuf libffi

# If still failing
brew install weasyprint
```
