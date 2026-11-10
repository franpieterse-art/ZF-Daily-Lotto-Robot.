# ZF Daily Lotto Robot V1
Upload these files to a NEW GitHub repository and deploy as a Render Python web service. Build: `pip install -r requirements.txt`; start: `gunicorn server:app`.

Press Sync free archive to load Daily Lotto history from the independent BetTip feed. If unavailable, import CSV with `game,date,numbers` where numbers are quoted comma-separated values, e.g. `Daily Lotto,2026-01-01,"1,2,3,4,5"`. Optional `RESULTSZA_API_KEY` allows date-specific results fallback. Never commit the key.

IMPORTANT: On Render free services, local files are ephemeral. For persistent learning and history, add a persistent disk on a supported plan or move JSON storage to a database. The app does not claim to predict random draws reliably. Six-number research rows are NOT standard Daily Lotto five-number tickets. Backtests are strictly chronological; learning chooses weights on a training portion and compares on later holdout dates. Multiple comparisons and small samples can still overfit. Verify third-party results against official sources.
