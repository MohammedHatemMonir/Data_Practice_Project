
# AI-Powered Decision Support System — Transport Emissions (Australia)

Predictive analytics on Australian transport-sector emissions, built
from seven public government datasets: cleaning, EDA, and
forecasting/regression models over a single, flat pipeline.

> **Scope note:** this project was originally framed as "road transport
> emissions." The published state-level emissions data only breaks down
> to whole transport sector (road + rail + domestic aviation + shipping
> combined) — there's no further mode split at that granularity in the
> real data. Rather than claim road-specific results the data can't
> support, the project's scope was renamed to match what's actually
> measurable. See [CHANGELOG.md](./CHANGELOG.md) for the full reasoning.

## Status

**Real government data is loaded and verified working.** All 7 sources
in scope currently resolve to real downloaded files (see
[Data sources](#data-sources)).

**Implemented and verified end-to-end:**

- Data loading + cleaning for all 7 sources, real-file-aware
  (`src/analysis/clean.py`)
- Merged, analysis-ready tables (annual state-level, monthly fuel series)
- Exploratory data analysis — 6 figures (`src/analysis/eda.py`)
- Two models — annual emissions regression, monthly fuel forecast
  (`src/analysis/model.py`)
- Data quality validation — emission-factor cross-check
  (`src/analysis/validate.py`)
- 24 automated tests (`tests/test_clean.py`, run with `pytest tests/`)
- CI on every push/PR (`.github/workflows/ci.yml`)
- Single command to run the whole pipeline (`run_pipeline.py`)
- Architecture and workflow diagrams (`docs/`)

**Also implemented (added on top of the simplified pipeline above):**

- A real DBMS "Gold" layer — `src/db.py` loads every processed table
  plus flattened model metrics into SQLite (or Postgres, via
  `DATABASE_URL`) — see [Database](#database-gold-layer) below.
- An interactive Streamlit dashboard and a FastAPI scoring endpoint —
  see [Deployment](#deployment) below. `dashboard/index.html` (the
  static, no-server dashboard) stays as-is; these are additional,
  live/served surfaces.
- Lightweight data-drift monitoring (`monitoring/monitor.py`) — see
  [Monitoring](#monitoring--data-drift) below.

This intentionally revisits one item from the "explicitly out of scope"
list below (a DBMS layer, a dashboard app, and an API) in a form sized
for a 4-person student project — one file each, not a layered
warehouse — rather than reinstating the original, more complex
Bronze/Silver/Gold architecture the CHANGELOG explains was removed.

**Still explicitly out of scope** — see [CHANGELOG.md](./CHANGELOG.md) for why:

- The original layered Bronze/Silver/Gold connector architecture
  (`src/ingest/*.py`, `BaseConnector`, a Silver Parquet layer) — still
  descoped; the DBMS/dashboard/API added above are new, simpler
  implementations, not a revival of that old code.
- **National GHG Accounts OData API and NSW Traffic Volume Counts** —
  descoped. Never had a real data pull wired in; removed from the
  pipeline, tests, and diagrams rather than kept as an undocumented
  half-feature. Not a gap to fill later — a deliberate scope decision.

## What running on real data actually showed

The regression (fuel + VKT + vehicles → transport-sector emissions)
scores **CV R² ≈ 0.995** on real data. That is expected, not a triumph
to celebrate uncritically: state emissions inventories are *constructed
from* fuel sales via published NGA emission factors, so a near-perfect
score here mostly reflects that accounting identity, not a novel
predictive insight.

The **fuel forecast** is the model actually worth trusting: MAPE ≈3.8%
on real monthly petroleum sales, since Holt-Winters is fitting genuine
seasonal structure.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # local config -- see .env.example for what each value does

pytest tests/           # 30 tests, ~3-4 min
python run_pipeline.py  # clean -> EDA -> model -> validate -> load into DBMS
```

For the full walkthrough (venv, `.env`, running the dashboard/API,
monitoring, and which other tools to install), see
[GUIDE.md](./GUIDE.md).

Outputs land in:

| Output                   | Location                                           |
| ------------------------ | -------------------------------------------------- |
| Cleaned, merged tables   | `data/processed/*.csv`                           |
| EDA figures              | `reports/figures/*.png`                          |
| Model metrics (JSON)     | `reports/model_results/metrics.json`             |
| Trained regression model | `reports/model_results/emissions_regression.pkl` |
| Data quality checks      | `reports/validation/*.csv`, `*.png`            |

Every pipeline run logs, per source, whether it used real data or a
fixture — check this before citing any number:

```
INFO: Using real data for 'petroleum_statistics': data/bronze/Australian Petroleum statistics consumption cover/...
```

## Data sources

| # | Source                                                   | Loader                           | Used by                                                                             |
| - | -------------------------------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------- |
| 1 | Australian Petroleum Statistics                          | `load_petroleum_statistics()`  | annual master, monthly forecast, validation                                         |
| 2 | State & Territory GHG Inventories (Emission Data Tables) | `load_state_territory_ghg()`   | annual master (regression target), validation                                       |
| 3 | National GHG Accounts Factors 2025                       | `load_nga_factors()`           | validation (emission-factor check)                                                  |
| 4 | BITRE Yearbook 2025 (VKT)                                | `load_bitre_yearbook()`        | annual master                                                                       |
| 5 | Registered Road Vehicles                                 | `load_vehicle_registrations()` | annual master (genuine annual series, sourced from the BITRE Yearbook — see below) |
| 6 | Quarterly GHG Update                                     | `load_quarterly_ghg_update()`  | loaded, not merged — no state dimension exists in this source                      |
| 7 | ABS Population (ERP)                                     | `load_population()`            | annual master with population                                                       |

Note: source 5's real data comes from the *same physical file* as
source 4 (the BITRE Yearbook workbook) — `Table 4.3` for VKT, `Table 4.6b` (inside the combined `Table 4.6a-c` sheet) for vehicle stock by
state. `load_vehicle_registrations()` locates the `bitre_yearbook` file
directly rather than a separate `vehicle_registrations` file for this
reason.

All real files currently live under human-named folders (whatever the
person who downloaded them called it), not the canonical `source_name`
keys — e.g. `data/bronze/Australian Petroleum statistics consumption cover/`. `clean.py`'s `BRONZE_FOLDER_ALIASES` maps every folder name
we've seen used to its canonical source; add to that dict if a new
folder name shows up rather than renaming folders to match.

## Real-data caveats — read before writing these into the report

1. **Emissions = whole transport sector, not road-only** — the reason
   for the project rename. The Emission Data Tables' finest state-level
   breakdown is `"3. Transport"` — road + rail + domestic aviation +
   shipping combined. No further mode split exists at state level in
   this published source.
2. **ACT has no state-level fuel sales data.** Confirmed against the raw
   source file's own `State` column — not a parsing gap. `annual_master`
   covers 7 states, not 8.
3. **The emission-factor validation gap (~30%) is expected.**
   `validate_emission_factors()` compares *road-fuel-only* implied
   emissions against the *whole-transport-sector* reported figure (see
   caveat 1) — implied should run lower, roughly in proportion to
   road's share of transport fuel use.

## Analysis-ready tables

Built by `clean.py`, aligned to Australian financial year (labelled by
its start year, e.g. "2020" = FY2020-21):

- **`annual_master.csv`** — fuel consumption, road VKT, registered
  vehicles, and transport-sector emissions (the regression target).
  Currently 98 rows: 7 states × 2010–2023.
- **`annual_master_with_population.csv`** — adds population and
  per-capita features.
- **`monthly_fuel_series.csv`** — the fuel forecasting target, ~190
  monthly points per state.

## Models

**`fit_emissions_regression()`** — linear regression and random
forest, 5-fold cross-validated. Reports CV R², CV MAE, and random-forest
feature importances.

**`forecast_fuel_consumption(state, test_months)`** — Holt-Winters
exponential smoothing with a seasonal-naive fallback if `statsmodels`
fails (happened on one teammate's environment — a real `statsmodels`
bug, fixed by upgrading to ≥0.15.0, see `requirements.txt`). `run()`
calls this once per state (all 7), not just one — results land in
`metrics.json` as `fuel_forecast_NSW`, `fuel_forecast_VIC`, etc., and
each gets its own chart (`reports/figures/06_forecast_<STATE>.png`).

> Every model result's `_caveat` field is generated at runtime, not
> hardcoded — check that run's "Using real data" / "Using sample data"
> log lines for the actual answer on whether real or fixture data
> produced a given number.

## Data quality validation

`src/analysis/validate.py` — **`validate_emission_factors()`**: fuel ×
published NGA factor vs. reported emissions. See caveat 4 above for why
a ~30% gap is expected, not a bug.

(A second check, comparing this data against a National Greenhouse
Accounts OData API pull, previously existed here. Removed along with
that data source — see CHANGELOG.md.)

## Dashboard

`dashboard/index.html` — an interactive dashboard, self-contained
(Plotly bundled locally as `dashboard/plotly.min.js`, no CDN, no
internet needed, no server — open the file directly in a browser).

- **Historical trends** — Transport-sector emissions, fuel consumption,
  VKT, registered vehicles, and both per-capita views, switchable via
  the metric dropdown, by state.
- **Per-state controls** — show/hide any state, recolor any line via
  the color swatch. Every panel below (monthly fuel, forecast bars)
  shares the same state selection and colors.
- **Monthly fuel consumption** — the real ~190-point-per-state series,
  not just the annual aggregate.
- **Models** — regression CV R²/MAE, a forecast-accuracy bar chart per
  state, and a detail view (train / actual / forecast) for any one
  state's fuel forecast.
- **Validation** — the emission-factor check as an interactive scatter.

Every caveat from this README (CV R² near 1 being expected, not a
predictive triumph; the ~30% validation gap being explained by
road-fuel-only vs. whole-transport-sector scope) is shown directly in
the dashboard, not just documented here — a marker or teammate looking
at the dashboard alone still gets the honest interpretation, not just
the chart.

Regenerate after any pipeline change:

```bash
python run_pipeline.py && python scripts/build_dashboard.py
```

`dashboard/template.html` is the source (HTML/CSS/JS); `build_dashboard.py`
reads the real processed data and injects it as embedded JSON — nothing
is fetched at runtime, so there's no CORS/network dependency when
someone just opens the file.

## Database (Gold layer)

`src/db.py` loads every table `clean.py` produces, plus the flattened
model/validation metrics, into a real DBMS — the "Evaluation" and
"Deployment" stages of the project lifecycle read from here, not from
loose CSVs.

- **Default: SQLite**, `data/gold/warehouse.sqlite` — zero setup, a
  single file, good enough for this project's size.
- **Optional: Postgres** (or anything else SQLAlchemy supports) — set
  `DATABASE_URL` in `.env` and nothing else in the code changes. See
  `.env.example` for the exact connection string format and a one-line
  Docker command to run Postgres locally.

Tables written: `annual_master`, `annual_master_with_population`,
`monthly_fuel_series`, `model_metrics` (one row per metric, flattened
from `metrics.json`, including nested feature importances), and
`pipeline_runs` (an audit log — one row per pipeline run, with a
timestamp and row counts, so "did this actually run recently" has an
answer in the DB itself).

Runs automatically as Step 5 of `python run_pipeline.py`. To run it on
its own (e.g. after only re-running one stage):

```bash
python -m src.db
```

Inspect the database directly:

```bash
sqlite3 data/gold/warehouse.sqlite ".tables"
sqlite3 data/gold/warehouse.sqlite "SELECT * FROM pipeline_runs;"
```

Or open `data/gold/warehouse.sqlite` in a GUI DB browser (DBeaver, or
the free "DB Browser for SQLite") if a point-and-click view is easier
than the CLI.

## Deployment

Two live, servable surfaces on top of the DBMS above (in addition to
the static `dashboard/index.html`, which stays as the no-server option):

**Interactive dashboard (Streamlit):**

```bash
streamlit run app/streamlit_app.py
```

Opens at `http://localhost:8501` — historical trends (with state/metric
selectors), monthly fuel, model results (regression + per-state
forecast MAPE), and a Monitoring tab showing the latest drift report.

**Scoring API (FastAPI):**

```bash
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs at `http://localhost:8000/docs`. Endpoints:
`GET /health`, `GET /states`, `GET /metrics`, `GET /monitoring/drift`,
`POST /predict` (scores the trained regression model on new
fuel/VKT/vehicle inputs).

Both read from the DBMS (`src/db.py`), so run `python run_pipeline.py`
at least once first to populate it.

## Monitoring & data drift

`monitoring/monitor.py` — Stage 8 of the project lifecycle. Compares
the current `annual_master.csv` against a saved reference snapshot,
column by column, using a Kolmogorov-Smirnov test:

```bash
python monitoring/monitor.py
```

First run saves the current data as the baseline
(`reports/monitoring/reference_annual_master.csv`); every later run
compares against it and writes `reports/monitoring/drift_report.json`
(also shown in the Streamlit dashboard's Monitoring tab and via the
API's `GET /monitoring/drift`). Delete the reference file to
deliberately re-baseline after a real, expected upstream data change.

A heavier alternative (a full interactive HTML report instead of a
JSON summary) is Evidently AI — see the comment at the top of
`monitoring/monitor.py` for the one-line swap if that's preferred.

## Notebook

`src/analysis/analysis.ipynb` — same results as the pipeline, displayed
inline as well as saved. Calls the exact same functions in
`clean.py`/`eda.py`/`model.py`/`validate.py` directly, so there's no
duplicated plotting logic — running it also writes to `reports/`, same
as `python run_pipeline.py` does. Open it in Jupyter and run all cells.

## Testing

```bash
pytest tests/ -v
```

30 tests: 24 for the clean/EDA/model/validate pipeline (master-table
shape checks — row count > 0, valid state codes, no nulls, positive
values — rather than exact numbers, since `_locate()` prefers real data
whenever present and the real row counts differ from the fixture-only
case), plus 6 for the DBMS layer and drift monitoring
(`tests/test_db_and_monitoring.py`), run against a temporary SQLite file
so they never touch `data/gold/warehouse.sqlite`.

## Continuous Integration

`.github/workflows/ci.yml` runs on every push/PR: installs
`requirements.txt`, runs tests, runs the full pipeline, uploads outputs
as a build artifact.

## Diagrams

`docs/architecture/architecture_v3.png` and
`docs/workflow/workflow_v3.png` — v3 reflects the transport-emissions
rename and the 7-source scope. Earlier versions kept in `docs/` as
historical record, not deleted. Regenerate with:

```bash
python scripts/generate_diagrams.py
```

## Repository layout

```
src/analysis/
  clean.py       # load, standardise, merge -> data/processed/
  eda.py         # figures -> reports/figures/
  model.py       # train + evaluate -> reports/model_results/
  validate.py    # data quality check -> reports/validation/
  analysis.ipynb # interactive notebook, same functions as the pipeline
src/
  db.py          # load data/processed/ + metrics -> DBMS (data/gold/)
app/
  streamlit_app.py  # interactive dashboard, reads from the DBMS
  api.py            # FastAPI scoring endpoint + metrics/drift routes
monitoring/
  monitor.py     # data-drift check (KS-test) -> reports/monitoring/
tests/
  test_clean.py               # 24 tests
  test_db_and_monitoring.py   # 6 tests (DBMS + monitoring)
scripts/
  generate_diagrams.py
  build_dashboard.py   # -> dashboard/index.html
dashboard/
  template.html  # source (HTML/CSS/JS)
  index.html     # generated -- open this one
  plotly.min.js  # bundled locally, no CDN dependency
.github/workflows/
  ci.yml
run_pipeline.py
.env / .env.example  # local config (DB URL, ports) -- .env is git-ignored
fixtures/        # small synthetic sample data -- fallback only
data/bronze/     # real downloaded files (human-named folders) + fixture copies
data/processed/  # cleaned/merged output (generated)
data/gold/       # DBMS file (SQLite), generated by src/db.py
reports/         # figures + model results + validation + monitoring (generated)
docs/            # architecture and workflow diagrams
```

## Known gaps & next steps

- The four real-data caveats above should be stated explicitly anywhere
  these results are cited in the report.
- Individual per-teammate git commits — adopt the branch/PR flow below.

## Git Workflow

**Model: GitHub Flow** — one protected `main` + short-lived feature branches.

```
main ──●────────●────────●────────●──── (always working, protected)
        \        \        \        \
         feature/ feature/ feature/ feature/
         clean-   eda-     model-   docs-
         merge    figures  cv       readme
         ●──●──●  ●──●     ●──●──●  ●──●
              ↑ PR + review + squash-merge, then delete branch
```

### Branch naming

`<type>/<epic-slug>-<task-slug>`:

| Type         | When                  | Example                           |
| ------------ | --------------------- | --------------------------------- |
| `feature/` | New functionality     | `feature/model-forecast-cv`     |
| `fix/`     | Bug fix               | `fix/clean-null-state-codes`    |
| `test/`    | Tests-only change     | `test/model-regression-cv`      |
| `docs/`    | README/docs only      | `docs/readme-quickstart`        |
| `chore/`   | Tooling, config, deps | `chore/pin-statsmodels-version` |

### Commit messages — Conventional Commits

```
feat(clean): parse real petroleum sales sheet, road-fuel products only
fix(validate): align fuel to financial year before comparing to emissions
docs(readme): rename project scope to transport emissions
```

### PR workflow

1. `git checkout main && git pull`
2. `git checkout -b feature/<epic>-<task>`
3. Commit in small chunks, not one batch per epic — this matters for
   Assessment 2 Section 4, where each teammate links their own commits
4. Push early, open a draft PR for visibility
5. One approving review before merge
6. Squash-merge into `main`, delete the branch

> **Note on this repo's history:** commits before this point were made
> directly to `main` while the project was rebuilt solo after the
> architecture change (see CHANGELOG.md). Adopt the branch/PR flow above
> for all work from here forward, so each team member has individual,
> linkable commit evidence for their contribution page.
