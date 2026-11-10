# ZF Daily Lotto Robot V3 — Audit and Learning History

## Deployment
Upload the files in this folder to the ROOT of your GitHub repository.
Build: `pip install -r requirements.txt`
Start: `gunicorn server:app --timeout 120`
Set `DATA_DIR` to a writable persistent disk mount path (e.g. `/var/data`). Do not set `/var/data` unless a Render persistent disk is actually mounted there. On an ephemeral Render service, omit `DATA_DIR` (data will be lost on redeploy).
Optional `RESULTSZA_API_KEY` enables provider sync, subject to provider API validity and limits. CSV import remains available.

## New V3 features
- SQLite audit of every prediction, six-number rows, date, time, attempt, strategy weights, blind/post-reveal status.
- Reveal uses the stored prediction ID rather than trusting editable rows sent from browser.
- History records actual results, best row, mean matches, unique coverage.
- Learn stores baseline/challenger weights, holdout performance, promotion decision, timestamp.
- Smaller 30-draw learning batches to reduce synchronous request timeout. 20 training and 10 holdout draws, with 60 warmup draws; these are exploratory and statistically weak.
- `/api/history` provides audit data; `/api/history.csv` exports prediction audit.

## Important limitations
Historical prediction results are reproducible but do not demonstrate any predictive edge over random lottery draws. Repeated learning against the same holdout leads to overfitting. For robust validation, evaluate a genuinely untouched later time period and compare with random baseline. The app does not auto-sync without a valid provider key. Render ephemeral files are not durable.

## Verification
Python syntax and JavaScript syntax checked. Full Flask runtime integration not tested in this environment.
