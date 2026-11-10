# ZF Daily Lotto Robot V4

## Deploy to GitHub + Render
Upload the **contents** of this folder (not the enclosing folder) to the root of a new or existing GitHub repository. Create a Render Python web service connected to the repository.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn server:app --timeout 120`
- Optional environment variable: `DATA_DIR=/var/data` **only if a persistent disk is mounted at `/var/data`**.

The included `za_daily.csv` seeds the historical archive automatically on first access. No API key is required for the bundled historical draws. To import newer results, use the CSV import button. The optional ResultsZA sync requires your own `RESULTSZA_API_KEY`.

## Features
- Date-based 5 rows x 6 numbers; predictions depend only on prior draws.
- Predict Again creates a new saved attempt; after a date's result has been revealed, new attempts are marked post-reveal experiments.
- Reveal reports hits, misses, best row and distinct winning-number coverage.
- Recurrence reports repeated 4-number subsets of 5-number draws and repeated complete 5-number draws, with dates and gaps in days/draws.
- 500-draw chronological backtest and seeded random baseline. Current model weights may have been tuned on some of these dates, so this is exploratory, not a pristine final holdout.
- Adaptive learning compares weight candidates on earlier training dates and later validation dates; records decisions in SQLite.
- Prediction and learning history stored in SQLite; export predictions as CSV.

## Persistence
Without a Render persistent disk, the SQLite audit and updated weights may be lost on redeploy/restart. The bundled CSV is always retained in the repository. Do not set `DATA_DIR` to a nonexistent/unmounted path. Render free services may not support persistent disks; export history regularly.

## Validation
Python syntax checked. Live Flask integration tests were unavailable in the build environment because Flask could not be installed. Validate routes and run a small backtest after deployment before the full 500-draw run.

## Statistical note
Daily Lotto draws five numbers from 1 to 36. Six-number rows are research predictions, not normal 5-number tickets. Lottery draws are random; historical recurrence does not establish predictive ability. Avoid using post-reveal results for blind-test claims.
