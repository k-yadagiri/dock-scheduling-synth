# Dock / Yard / Labor Appointment Scheduling — Synthetic Data Generator

Schedules inbound/outbound carrier appointments against **dock, yard, labor, vehicle and time-window constraints**, simulates check-in → yard → service → departure (with no-shows, early/late arrivals, gate/dock congestion), injects **labelled anomalies**, and validates everything. Python 3.9+ standard library only (no installs).

## Run
```bash
python generate.py --scale full --out output/full --verify-repro   # 10 facilities, 100 docks, 20,000 appts, 60 days (~20 s)
python generate.py --scale starter --out output/starter            # same generator, small scale
python validate.py output/full                                      # re-run validation + metrics
python -m unittest discover -s tests -v                             # tests
```
Fixed seed `20261022` (override with `--seed`; scale via `--n-fac --docks-per --n-appt --days`). Pre-generated output is included in `output/`.

## How it works (rules, not random labels)
1. **Master data**: Facility, Dock (type IN/OUT/FLEX, reefer, hazmat, max vehicle length, effective dates; 5 docks open on day 20), YardSlot (standard/reefer-plug/hazmat), Carrier, Vehicle, HandlingRequirement (temp class × hazmat class → base + per-pallet service time), bridge `DockHandlingCapability` (N:M), LaborShift calendar (2 shifts/day, crews).
2. **Requests** (weighted by weekday, peak days, AM/early-PM peak hours, facility) → shipments (1–2 per appointment) → **allocation** in request order: earliest 15-min slot within +6 h where a compatible dock is free (direction, capability, vehicle length, effective date), the **vehicle** is free, a **labor crew** is available in every 15-min slot, and the visit ends within facility hours. Otherwise `REJECTED` with cause `NO_DOCK_CAPACITY` / `LABOR_CAPACITY`.
3. **Simulation**: no-show / late probability from carrier `on_time_score`; 18% early arrivals; peak-day gate queues; service duration = planned × lognormal factor; docks process sequentially so overruns propagate (**congestion**); yard slot chosen by type, `YARD_FULL` if none.
4. **Events are append-only** (`CheckInEvent`, ID `CHECK-<appt-id>-NN`); appointment `status` is derived from the last event. **Exceptions** carry cause codes derived from the simulation.
5. **Derived values** (pallet/weight totals, service minutes, end times, statuses, exceptions) are computed from source rows and re-checked by the validator.
6. **Injected anomalies** (0.2% of appointments each, `ground_truth/ground_truth.csv|json`): overlapping appointments exceed dock capacity, incompatible load assigned, check-in before appointment date, labor shift not available, no-show not recorded. Only the target rows are altered; each is labelled with `issue_type`, expected decision and violated rule. Per-appointment simulation outcomes are in `ground_truth/outcome_labels.csv`. Ground truth is never in `data/`.

## Output layout
`data/*.csv` (12 entity tables) · `sql/schema.sql` + `sql/seed.sql` (SQLite/ANSI) · `ground_truth/` · `docs/data_dictionary.md` (fields, types, enums, units, uniqueness, rules, cardinality, lifecycle) · `reports/validation_summary.json`, `reports/metrics_summary.json` · `manifest.json` (seed, params, command, row counts, SHA-256 per file, source manifest) · `reproducibility_report.json`.

## Validation (`validate.py`)
PK/unique, FK integrity, required/type/enum/ID-pattern, date & event-time ordering, arithmetic reconciliation, lifecycle transitions, duplicates/vehicle double-booking — all **PASS** on the final data (anomalies are semantic, not structural). Five independent **business-rule detectors** (using only `data/`) must recover exactly the ground-truth rows (precision = recall = 1.0). Metrics (utilization by facility/hour, wait/dwell mean/p50/p90, no-show/early/late/rejection rates, exceptions by cause) are reproducible from the CSVs.

## Reproducibility
`--verify-repro` regenerates twice and compares row counts and SHA-256 of all 20 files → `reproducibility_report.json` (`row_counts_match`, `checksums_match` = true). Timestamps are facility-local naive ISO-8601; no wall-clock values are written.

## Full-run snapshot (seed 20261022)
20,000 appointments (17,330 completed, 855 no-show, 1,775 rejected, 40 unrecorded no-shows), 26,049 shipments, 107,505 events, 8,680 exceptions; overall dock utilization 21%, peak-hour ~27%; wait check-in→service mean 31 min / p90 91 min.

## Provenance
No external data. Fully synthetic; no personal or confidential data.

## Known simplifications
One crew per appointment, dock capacity 1, single timezone-naive clock per facility, no appointment rescheduling after rejection.
