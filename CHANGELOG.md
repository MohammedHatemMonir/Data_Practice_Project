
# Changelog

## [Unreleased] - 2026-09-12 (DBMS, deployment, and monitoring layers added)

### Added — full lifecycle coverage: Database, Deployment, Monitoring

The pipeline previously stopped at Validation (Step 4/4). This adds the
remaining stages of the standard data-science project lifecycle, sized
for this project rather than reviving the earlier descoped
Bronze/Silver/Gold architecture (see the 2026-09-09 entries below for
why that was removed):

- **`src/db.py`** — a Gold storage layer. Loads every processed table
  and the flattened model/validation metrics into a real DBMS: SQLite
  by default (`data/gold/warehouse.sqlite`), or Postgres (or any
  SQLAlchemy-supported DB) by setting `DATABASE_URL` in `.env` — no
  code change needed to switch. Also writes a `pipeline_runs` audit
  table (timestamp + row counts per run). `run_pipeline.py` now runs 5
  stages (was 4): clean -> EDA -> model -> validate -> load to DB.
- **`app/streamlit_app.py`** — an interactive Streamlit dashboard
  reading live from the DBMS (historical trends, monthly fuel, model
  results, and a monitoring tab). Additive: `dashboard/index.html` (the
  static, no-server dashboard) is unchanged and still works exactly as
  before.
- **`app/api.py`** — a FastAPI service exposing the trained regression
  model for scoring (`POST /predict`), plus `/health`, `/states`,
  `/metrics`, and `/monitoring/drift`, all reading from the DBMS.
- **`monitoring/monitor.py`** — data-drift detection: a two-sample
  Kolmogorov-Smirnov test comparing the current `annual_master.csv`
  against a saved reference snapshot, per numeric column. First run
  saves the baseline; later runs flag drift and write
  `reports/monitoring/drift_report.json`. A comment in the module notes
  Evidently AI as a heavier, optional alternative — not adopted by
  default, to keep the dependency list small.
- **`.env` / `.env.example`** — local configuration (DB connection
  string, app ports, monitoring threshold). `.env` is git-ignored (was
  already covered by the existing `.gitignore`); `.env.example` is the
  committed template.
- **`tests/test_db_and_monitoring.py`** — 6 new tests (DB load,
  metrics-flattening including nested feature importances, audit-row
  recording, default DB URL, and both monitoring code paths — baseline
  creation and no-drift detection), run against a temporary SQLite file
  so they never touch the real `data/gold/warehouse.sqlite`.
- `requirements.txt` — added `python-dotenv`, `SQLAlchemy`, `scipy`
  (for the KS-test), `fastapi`, `uvicorn`, `streamlit`, `plotly`.
  Uncommented `openpyxl` — it was already a hard runtime dependency
  (every real-data loader in `clean.py` calls `pd.read_excel()`) but had
  been left commented out as merely "anticipated."
- `.github/workflows/ci.yml` — added a monitoring step after the
  pipeline smoke test, and `data/gold/` to the uploaded build artifact.

### Verified

- Full pipeline (`python run_pipeline.py`) runs clean end-to-end on
  real data, including the new Step 5 — confirmed `data/gold/
  warehouse.sqlite` contains all 5 expected tables with correct row
  counts (98 annual rows, 1344 monthly rows, 50 flattened metric rows).
- All 24 existing tests + 6 new tests pass (30 total, `pytest tests/`).
- `app/api.py`'s endpoints tested directly via FastAPI's `TestClient`
  (not just "the code looks right"): `/health`, `/states`, `/metrics`,
  `/monitoring/drift`, and `/predict` all returned real, correct data
  from the actual populated database and trained model.
- `monitoring/monitor.py` run twice in sequence: first run correctly
  created the baseline; second run (identical data) correctly reported
  `no_drift` with p=1.0 on every checked column.
- `app/streamlit_app.py` and all other new modules pass
  `python -m py_compile` (syntax/import check); Streamlit itself isn't
  automatable headlessly in this environment, so its widgets were
  reviewed against the DB schema and `metrics.json`'s real shape rather
  than click-tested — worth a manual `streamlit run` check after pulling
  this locally.

## [Unreleased] - 2026-09-09

### Changed — Architecture simplified: Bronze/Silver/Gold → single clean/EDA/model pipeline

**Previous state:** A layered "medallion" architecture (Bronze → Silver → Gold),
with per-source ingestion connector classes (`src/ingest/*.py`), a shared
`BaseConnector` with retry/backoff, an orchestration scheduler, a Silver
transform layer writing Parquet, and a Gold star-schema warehouse
(SQLite/DuckDB), feeding a separate ML layer and Streamlit dashboard.

**Current state:** A single `src/analysis/` module with three files —
`clean.py` (load + standardise + merge the 9 sources into analysis-ready
tables), `eda.py` (distributions, trends, correlations, all saved as
figures), and `model.py` (regression + time-series forecast, with
evaluation metrics). Run end-to-end with `python run_pipeline.py`.

**Justification:**

1. The connector/orchestration code for the previous architecture was lost
   in commit `d2942ca` (ingestion connectors, Silver parquet outputs, and
   the Gold warehouse were deleted; only `scheduler.py` remained). Rather
   than rebuilding equivalent complexity from scratch under time pressure,
   the team re-scoped the architecture to match what a 4-person student
   project can realistically build, test, and maintain for the remainder
   of the semester.
2. The assessment rubric requires evidence of data acquisition, cleaning,
   EDA, and predictive modelling — it does not require a layered warehouse
   architecture. The simplified pipeline satisfies every required rubric
   item with less surface area for things to break.
3. A single, flat, well-documented module is easier for four people to
   review and extend than five architectural layers, given the team's
   size and the remaining timeline.

**What was removed:** `src/ingest/` connector classes, `BaseConnector`,
the Silver Parquet layer, the Gold SQLite/DuckDB warehouse, the
FastAPI scoring endpoint, and the Streamlit dashboard scaffold. None of
these had been demonstrated working end-to-end in this repo before removal.

**What replaced it:** `src/analysis/clean.py`, `src/analysis/eda.py`,
`src/analysis/model.py`, orchestrated by `run_pipeline.py`. Verified
to run end-to-end from a clean checkout, producing:

- `data/processed/` — cleaned, merged CSVs
- `reports/figures/` — 6 EDA/forecast figures
- `reports/model_results/metrics.json` — cross-validated regression
  metrics + monthly fuel forecast metrics, with a trained model `.pkl`

### Removed (commit `d2942ca`, prior to this entry — documented retroactively)

- All `src/ingest/*.py` connector modules
- `data/silver/*.parquet`
- `data/gold/warehouse.sqlite`

This removal was not documented in a changelog at the time it happened.
This entry exists to bring the project change record up to date and
establish going-forward practice: every architecture/scope change from
here on gets an entry here before the next assessment is submitted.

## [Unreleased] - 2026-09-09 (later same day)

### Removed — legacy `src/ingest/` layer and its Silver/Gold outputs, permanently

After the above decision, `src/ingest/*.py` and the Silver/Gold artefacts
were briefly restored via `git revert` while the team confirmed the
decision. On inspection, the restored code turned out to be non-functional:
every connector imports `src.common.config` and
`src.common.logging_setup`, and **`src/common/` does not exist in this
repository's history on any branch** — it was never committed. The
Silver `.parquet` files and `data/gold/warehouse.sqlite` that *were*
committed are valid, populated data (verified: correct schema, correct
row counts against the fixtures) — but there is no working code in this
repo that can regenerate them.

**Decision:** remove `src/ingest/`, `data/silver/`, and `data/gold/`
permanently rather than reconstruct `src/common` from scratch. Rebuilding
it would only resurrect a pipeline that produces output nothing else in
the repo consumes — `src/analysis/` already covers acquisition (via
`data/bronze/`), cleaning, EDA, and modelling end-to-end. Keeping
non-runnable code in the repo actively works against the assessment's
"reproducibility artefacts" and "execution instructions" requirements:
anyone following the setup instructions and running the legacy path
would hit an `ImportError` on the first import.

**Verified after removal:** `python run_pipeline.py` still runs
end-to-end with no errors — `src/analysis/` never depended on
`src/ingest/`, `data/silver/`, or `data/gold/` in the first place.

From this point on, `src/analysis/` (via `run_pipeline.py`) is the
single, sole data pipeline for this project.

## [Unreleased] - 2026-09-09 (hardening pass)

### Added

- Loaders for the two previously-unused sources: `load_nga_odata_api()`
  and `load_nsw_traffic_counts()` in `clean.py`. All 9 sources now have
  a loader (source 7, quarterly GHG update, is loaded/tested but not yet
  consumed by a table — noted as a next step in README).
- `src/analysis/validate.py` — two data-quality checks that were
  previously just "future work": an emission-factor cross-check
  (fuel × published factor vs. reported inventory) and a dual-source GHG
  consistency check (published CSV table vs. the same data via the
  OData API).
- NSW hourly traffic EDA figure and a 24-hour-seasonality forecast model
  (`forecast_nsw_traffic()`), using the same method as the existing fuel
  forecast for consistency.
- `tests/test_clean.py` — 22 tests: state-code standardisation, every
  loader, exact row counts for every master table, and `_locate()`'s
  fallback ordering (tested in isolation via `tmp_path`, not against the
  real `data/bronze/`).
- `.github/workflows/ci.yml` — runs the test suite and a full pipeline
  smoke test on every push/PR to `main`, uploads generated outputs as a
  build artifact.
- `docs/architecture/architecture_v2.png` and
  `docs/workflow/workflow_v2.png`, generated by
  `scripts/generate_diagrams.py`, matching the current pipeline exactly.

### Changed

- `requirements.txt` trimmed from 24 packages to the 6 actually imported
  anywhere in `src/analysis/`, `run_pipeline.py`, or `tests/` (pandas,
  numpy, matplotlib, scikit-learn, statsmodels, pytest) — verified by
  grepping every import statement against the file. `openpyxl` and
  `requests` kept as commented-out "anticipated" entries for when real
  `.xlsx` sources and a download script are added.
- `run_pipeline.py` now runs 4 stages (clean → EDA → model → validate),
  was 3.

### Verified

- Full pipeline re-run end-to-end after every change in this pass
  (`python run_pipeline.py`, exit 0, all expected output files present).
- All 22 tests pass (`pytest tests/`).

## [Unreleased] - 2026-09-10 (real data integration)

### Changed — clean.py rewritten to parse real government files, not just fixtures

Every loader that has a real file available (7 of 9 sources) now branches
on the actual file's structure instead of assuming the fixture's flat,
pre-cleaned shape. Real government spreadsheets are genuinely different
from the fixtures in ways that needed real code changes, not just format
detection:

- **Folder resolution**: real downloads sit in human-named folders
  (`"Australian Petroleum statistics consumption cover"`, not
  `petroleum_statistics`), with no dated subfolder. Added
  `BRONZE_FOLDER_ALIASES` and rewrote `_locate()` to search every known
  alias, both directly in the folder and in any dated subfolder within
  it.
- **Financial year alignment**: state emissions (`state_territory_ghg`)
  and VKT (`bitre_yearbook`) are natively financial-year data; petroleum
  sales and population are calendar-dated. Added `_fy_start_from_date()`
  and `_parse_financial_year()` so every source aggregates to the same
  FY convention before joining — previously (see bug below) these were
  silently misaligned.
- **Wide-to-long reshaping**: petroleum sales (`Sales by state and territory` sheet), BITRE VKT (`Table 4.3`), and population (`Data1`
  sheet, ABS's standard wide export) are all wide-format in the real
  files (states or sex/state combinations as columns) and needed melting
  to the long shape the rest of the pipeline expects.
- **Multi-sheet, multi-row-header parsing**: `state_territory_ghg` is
  one sheet per state with a merged-cell IPCC category hierarchy;
  `nga_factors_2025`'s Table 9 has a 3-row header with a
  forward-filled "Transport type" column. Both needed explicit
  `skiprows`/`header=None` parsing rather than a direct `read_excel`.
- **Real emission factors are two-step, not a single lookup**: Table 9
  gives Energy Content (GJ per unit of fuel) and a separate Combined
  Scope 1 factor (kg CO2-e/GJ) — `load_nga_factors()` now computes
  `factor_kg_co2e_per_l = energy_content * combined_factor / 1000`
  instead of reading a single pre-computed column, which only existed in
  the fixture's simplified shape.

### Fixed — FY-alignment bug in validate.py

`validate_emission_factors()` was grouping fuel consumption by calendar
year while `state_territory_ghg`'s `year` is a financial-year start —
misaligning up to ~6 months of transactions per state-year before this
fix. Now groups by fuel's `fy_year` (computed the same way as every
other source) before comparing. Same class of bug as the earlier
`-N:-N+test_len` slicing issue in `model.py` — an unstated unit/convention
mismatch between two pieces of code that individually looked correct.

### Fixed — three "_caveat" fields that would have been actively false

`model.py`'s three result caveats unconditionally said "synthetic
fixture data," left over from before real data was loaded. On a real-data
run this claim is simply wrong. Replaced with `_data_source_caveat()`,
which points to that run's actual log output instead of asserting either
case — correct regardless of which data was loaded. Same fix applied to
a matching false claim in `eda.py`'s correlation heatmap docstring/title.

### Findings from real data — significant enough to change how results are described

- **State-level emissions cover the whole transport sector** (road +
  rail + domestic aviation + shipping) — the published Emission Data
  Tables don't break this down further by mode at the state level. Every
  place that used to say "road transport emissions" now says
  "transport-sector emissions."
- **ACT has no state-level entry in the petroleum sales source** —
  confirmed against the file's own `State` column. `annual_master` covers
  7 states, not 8.
- **Vehicle registrations is a fleet-by-manufacture-year snapshot**, not
  an annual registrations time series (filename contains `yom`).
  `build_annual_master()` now explicitly broadcasts each state's current
  total as a constant across all years, with a runtime warning, rather
  than silently treating manufacture year as if it were registration
  year.
- **The activity table originally downloaded for source 2 was the wrong
  file** — it's the national fuel-consumption Activity Table (PJ by
  vehicle category, no state breakdown), not the state-level Emission
  Data Tables. The correct file was located and re-downloaded (see
  `data/bronze/State & Territory Inventories 2024 - Emission Data Tables/`); the original activity table remains in the repo but is not
  currently used by any loader.

### Verified — real numbers sanity-checked against independent published figures

- ACT transport-sector emissions ~1,080–1,130 kt CO2-e (2019–2023) —
  same order of magnitude as ACT's total reported emissions from an
  independent source (~1.1–1.4 Mt across all sectors), consistent with
  transport being roughly 60% of ACT's total per that same source.
- NSW VKT ~77.5 billion km (2024-25) — consistent with NSW's share of
  the ~264 billion km national total reported by BITRE.
- Real-vs-fixture regression comparison: CV R² went from **-0.29**
  (synthetic, expected for independently-random data) to **0.995**
  (real, expected for accounting-identity-derived data) — the
  theoretically-predicted direction in both cases, which is stronger
  evidence the pipeline is correct than either number alone.
- Full pipeline (`python run_pipeline.py`) and full test suite (28
  tests, `pytest tests/`) both verified passing against the real-data
  environment, not just fixtures, before this entry was written.

### Test suite changed — structural checks instead of hardcoded fixture counts

`test_annual_master_shape()` and related tests previously asserted exact
numbers (48 rows, 8 states, 6 years) that were only ever true for the
fixture-only case. Since `_locate()` now prefers real data whenever
present, these numbers are environment-dependent by design. Rewrote
these tests to check structure (row count > 0, valid state codes, no
nulls, positive values) instead — meaningful in both the fixture-only
and real-data cases, rather than passing on a fresh clone and failing
the moment real data is added. Added dedicated tests for
`_parse_financial_year()`, `_fy_start_from_date()`, and folder-alias
resolution. 28 tests total, up from 22.

## [Unreleased] - 2026-09-10 (scope decisions)

### Changed — project renamed from "Road Transport Emissions" to "Transport Emissions"

**Previous state:** Project title, README, chart titles, and docstrings
described the target variable as "road transport emissions."

**Current state:** Renamed to "Transport Emissions (Australia)"
throughout — title, README, `scripts/generate_diagrams.py`'s diagram
title, and relevant docstrings/comments in `validate.py` and `clean.py`.

**Justification:** confirmed directly against the real government data
(see the "real data integration" entry above) that the published
state-level Emission Data Tables only break down to whole transport
sector — road + rail + domestic aviation + shipping combined. There is
no further mode split at the state level in this authoritative source.
Continuing to call the project's output "road transport emissions"
would overclaim precision the underlying data doesn't support. The
rename costs nothing scientifically and is the more defensible framing
against the actual source.

Note: predictor variables that genuinely are road-specific (fuel sales,
VKT, vehicle registrations) keep language describing them as road-fuel
or road-vehicle inputs where that's accurate — the rename applies to the
project's overall scope and its target variable, not to inputs that
really are road-specific.

### Removed — National GHG Accounts OData API and NSW Traffic Volume Counts sources

**Previous state:** Both sources had loaders (`load_nga_odata_api()`,
`load_nsw_traffic_counts()`), fixture data, a validation check
(`validate_ghg_cross_source()`), an EDA figure, and a forecast model
(`forecast_nsw_traffic()`) — but neither ever had a real data pull wired
in; both ran on synthetic fixtures throughout the project.

**Current state:** Both removed entirely — loaders, fixture files
(`fixtures/nga_odata_api.SAMPLE.json`, `fixtures/nsw_traffic_counts.SAMPLE.csv`),
the cross-source validation check, the NSW traffic EDA figure, the NSW
traffic forecast model, and their entries in `BRONZE_FOLDER_ALIASES`.
Corresponding tests removed from `tests/test_clean.py` (28 → 24 tests).
Architecture diagram regenerated as v3 to reflect 7 sources instead of 9.

**Justification:** with real data now loaded for the other 7 sources,
team time is better spent deepening and reporting on those than
maintaining two sources that were never going to have real data before
submission. Keeping them in as documented "future work" was considered
and rejected — an honest accounting of remaining scope is better served
by removing incomplete features cleanly than by listing them
indefinitely as pending.

### Verified

- Full pipeline (`python run_pipeline.py`) and full test suite (24
  tests, `pytest tests/`) both pass after both changes.
- Confirmed no orphaned references: grepped for "road transport",
  "nga_odata", and "nsw_traffic" across `.py`/`.md` files after the
  changes; remaining "road" mentions are accurate descriptions of
  road-specific inputs (fuel, VKT), not the project's overall scope.

## [Unreleased] - 2026-09-10 (all-states forecast)

### Fixed — fuel forecast and its EDA chart only covered NSW, despite having all 7 states' data

`model.py: run()` called `forecast_fuel_consumption("NSW")` once,
hardcoded to one state, even though `monthly_fuel_series.csv` has real
data for all 7 states in scope. Same issue in
`eda.py: plot_monthly_fuel_series()`, which only plotted NSW by default.
This was a scope choice made when the function was first written (one
example state to prove the method worked), not a data limitation --
worth being clear about, since the data was never the constraint.

**Changed:**

- `model.py: run()` now loops over every state present in
  `monthly_fuel_series.csv` and forecasts each one. Results land in
  `metrics.json` under `fuel_forecast_<STATE>` per state; each gets its
  own chart, `reports/figures/06_forecast_<STATE>.png`.
- `eda.py: plot_monthly_fuel_series()` rewritten from a single-state
  line chart to a 7-panel small-multiples grid, one panel per state,
  independent y-axis scales per panel (NT and TAS's volumes are roughly
  15x smaller than NSW/VIC's -- a shared scale would flatten them to an
  invisible line).

**Verified:** all 7 states forecast successfully, MAPE ranging 2.7%
(WA) to 12.9% (NT, the smallest and most volatile state by volume) --
sensible variation, not a bug. Every state's monthly chart shows the
same COVID-era dip around early 2020, which is exactly the kind of
cross-state consistency that's reassuring to see in genuinely real data.

## [Unreleased] - 2026-09-11 (notebook for inline display)

### Added — src/analysis/analysis.ipynb

Every plotting/reporting function in `eda.py`, `model.py`, and
`validate.py` now takes a `save: bool = True` parameter. Default
behaviour (used by `run_pipeline.py`/CI) is unchanged -- saves to
`reports/` exactly as before. The notebook calls the same functions
with `save=False`, so charts render inline in the notebook cell and
nothing is written to disk -- no duplicated plotting code, no export
side effect from running the notebook.

Verified, not assumed: executed the notebook headlessly via `nbclient`
and inspected the output cells directly -- 13 inline PNG images
rendered (5 EDA figures, 7 per-state forecast figures, 1 validation
figure), 0 errors, and `reports/`'s file count was identical (16 files)
before and after running it, confirming zero export occurred.

Note: `matplotlib.use("Agg")` (needed so the CLI/CI path runs headless)
does not auto-render in Jupyter the way the default "inline" backend
does -- a bare Figure as a cell's last expression produced no image
output at all when first tried. Fixed with a small `show(fig)` helper
in the notebook that rasterises the figure to PNG bytes in memory and
displays those directly, which works regardless of which backend is
active.

## [Unreleased] - 2026-09-11 (simplified notebook -- dropped save parameter)

### Changed — reverted the save=True/False parameter added in the previous entry

That approach worked but added a parameter every plotting function had
to carry, purely to support one use case (the notebook). Decided it
wasn't worth the complexity: `eda.py`, `model.py`, and `validate.py`'s
functions now always save (no parameter, back to how they were before
that entry) -- `analysis.ipynb` calls them directly and additionally
displays what's returned. Running the notebook now also writes to
`reports/`, same as `python run_pipeline.py` -- this is an intentional
simplification, not an oversight.

Also fixed the AttributeError a teammate hit
(`'NoneType' object has no attribute 'savefig'`) — caused by an
already-running kernel still holding the *original* pre-return-value
version of these functions in memory after the file on disk had been
updated. Editing a `.py` file does not reload it in a live kernel;
noted this explicitly at the top of the notebook now.

Verified: full pipeline + 24 tests pass, and the notebook was executed
headlessly end-to-end -- 13 inline images rendered, 0 errors, and all
16 expected files present in `reports/` afterward (same as a normal
pipeline run).

## [Unreleased] - 2026-09-11 (interactive dashboard)

### Added — dashboard/index.html

Interactive, self-contained dashboard (`dashboard/`): historical trends
(emissions, fuel, VKT, vehicles, per-capita) with per-state show/hide
and recolor controls, monthly fuel consumption, model results
(regression stats, forecast-accuracy bar chart, per-state forecast
detail), and the emission-factor validation as an interactive scatter.
Every caveat already documented in this README (CV R² near 1 being
expected, not a predictive win; the ~30% validation gap being explained
by scope, not error) is shown directly in the dashboard's own UI, not
left for someone to find only by reading the docs separately.

`scripts/build_dashboard.py` reads the real processed data and embeds
it as JSON directly in the HTML -- no fetch(), no CORS, no server, no
network dependency at runtime. `model.py`'s `forecast_fuel_consumption()`
was extended to also return the full train/actual/forecast series (not
just summary MAE/MAPE), needed for the dashboard's forecast-detail
chart -- additive, doesn't change existing behaviour.

### Fixed — bundled Plotly.js locally instead of using a CDN

First version linked `https://cdn.plot.ly/...`. Verified with a real
headless browser (Playwright) before calling this done, rather than
assuming a CDN `<script>` tag just works -- and it didn't: the CDN
request failed in testing, leaving `Plotly is not defined` and a
completely blank dashboard. Fixed by bundling `plotly.min.js` locally
in `dashboard/` (via `npm install plotly.js-dist-min`) so the dashboard
has no runtime network dependency at all -- it works exactly the same
whether opened online, offline, or on a network that blocks the CDN.

### Fixed — three charts (monthly fuel, forecast bar, forecast detail) rendering completely blank

Real bug, found by actually loading the page and screenshotting it, not
by reading the code: `PLOT_LAYOUT_BASE`'s nested `xaxis`/`yaxis` objects
were shared by reference across all charts. Spreading `{...PLOT_LAYOUT_BASE}`
only shallow-copies the top-level object -- the nested `xaxis`/`yaxis`
sub-objects stayed shared. Plotly mutates whatever axis object it's
given (attaching computed `range`, `autorange`, `type` after rendering),
so after the first chart rendered (a numeric year axis, range
~2009-2024), every later chart inherited that exact same mutated axis
object -- including charts that needed a date-string axis, which then
silently failed to plot against a numeric range meant for years.

Confirmed the root cause directly (not just patched and hoped) by
inspecting `PLOT_LAYOUT_BASE.xaxis` in a live page after rendering:
it had picked up `type: "linear", range: [2009.2, 2023.8]` from the
first chart. Fixed with a `freshLayout()` helper that constructs a
brand-new `xaxis`/`yaxis` object on every call -- no chart shares any
nested object with any other chart.

### Verified

- Full pipeline (24 tests, `python run_pipeline.py`) and the dashboard
  rebuild (`python scripts/build_dashboard.py`) both run clean.
- Loaded the actual generated `dashboard/index.html` in a real headless
  browser (Playwright): 0 console errors, 0 page errors, full-page
  screenshot inspected directly.
- Interactivity tested by real DOM manipulation, not assumed: unchecking
  a state removes its trace; switching the metric dropdown updates the
  chart and title; changing a state's color updates the rendered line
  color; changing the forecast-detail state selector updates that
  chart's three traces. All four confirmed via direct JS-state
  inspection after each action, not just "it looks right."

## [Unreleased] - 2026-09-11 (dashboard caveat for flat vehicle registrations)

### Fixed — dashboard didn't explain why "Registered vehicles" is flat every year

The chart itself was correct (matches the real data exactly — see the
vehicle-registrations caveat elsewhere in this file), but nothing in
the dashboard UI told a viewer *why* it's flat, so it read as a bug
rather than a documented data limitation. Added a per-metric note
(`METRIC_LABELS.registered_vehicles.note`) that displays directly above
the chart whenever that metric is selected, explaining the
manufacture-year-snapshot limitation in place, the same way the
regression and validation panels already surface their own caveats
rather than leaving them only in this file.

## [Unreleased] - 2026-09-11 (corrected vehicle registrations to a real annual series)

### Changed — load_vehicle_registrations() now sources from a genuine annual time series

**Previous state:** Used a real CSV that was a snapshot of the current
fleet broken down by year of *manufacture*, not registrations per year
-- there was no genuine year-to-year figure available from it, so
`build_annual_master()` broadcast each state's current total as a
constant across every year (flat line on every chart, correctly
explained but still a real data-quality limitation, not fixed).

**Current state:** Found a real fix rather than only documenting the
limitation -- the BITRE Yearbook workbook (already used for VKT,
`Table 4.3`) also contains `Table 4.6b`: genuine annual state-level
vehicle stock, 1982-2025, complete for the project's full 2010-2023
range. `load_vehicle_registrations()` now parses this directly (same
physical file as `load_bitre_yearbook()`, different section) instead of
the manufacture-year CSV. The old CSV-based path is kept as a
defensive fallback only, clearly logged as not the normal path if it's
ever hit.

**Justification:** the flat-line limitation was a real, if honestly
documented, weakness. Once a genuine alternative source was identified
in a file already in the repo, fixing it outright is better than
leaving a documented workaround in place. Removed the now-obsolete
"vehicle registrations is a snapshot" caveat from `README.md` and the
dashboard (`METRIC_LABELS.registered_vehicles.note`) -- leaving a
caveat in place after the underlying problem is fixed would itself be
inaccurate.

### Findings from the fix

- Regression fit improved: CV R² 0.9949 → 0.9966, CV MAE 456.7 → 368.8 kt.
- `registered_vehicles`' feature importance changed from 11.7% (least
  important of the three) to 40.0% (most important) -- with real
  year-to-year variation, it's now a genuinely informative predictor,
  not a constant a model could only exploit as an implicit per-state
  indicator.

### Verified

- 24 tests, full pipeline, and dashboard rebuild all pass clean.
- Confirmed real per-year variation directly (NSW: 4.68M in 2010 →
  6.16M in 2023, matching real fleet growth), not just "the code ran."
- Re-screenshotted the dashboard's "Registered vehicles" chart post-fix
  -- smooth real growth curves, not flat lines.
