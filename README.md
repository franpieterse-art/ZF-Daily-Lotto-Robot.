# ZF Daily Lotto Robot V2

## GitHub / Render
Upload the CONTENTS of this folder to the ROOT of a new or existing GitHub repository.
Render Python web service: Build command `pip install -r requirements.txt`; Start command `gunicorn server:app`.
In Render > Environment add `RESULTSZA_API_KEY` using a key you obtain from https://resultsza.co.za/api_docs . Do not paste API keys into GitHub.
Optional: set `DATA_DIR=/var/data` and attach a persistent Render disk mounted at `/var/data` on a plan that supports disks. Without it, historical results and learning weights can be lost on restart/deploy.

## How it works
Sync ResultsZA: choose start and end dates (max 61 days per request). Each day uses an API request unless previously saved. API plans may limit requests; the app does not include or bypass a provider key. A 404 for a day is skipped; other provider errors are reported. For a long archive, sync consecutive 61-day ranges or import a CSV (`date,n1,n2,n3,n4,n5` or `date,winning_numbers`).
Predict: requires 30 earlier draws. Produces five research rows of six numbers. The actual Daily Lotto draw is FIVE numbers; research rows are not valid standard tickets.
Reveal: compares to a stored result or requests the selected date from ResultsZA. Learn: tests weight variations on chronologically split history, and promotes only if the challenger improves on a later holdout. Training/holdout testing alone does not establish predictive power; repeated selection on the holdout risks overfitting.

No official lottery affiliation. Results from third-party services should be verified against official results. Random lottery outcomes cannot be forecast reliably by historical frequency, gaps, or machine learning.
