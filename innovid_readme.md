# Innovid API Pipeline

## What It Does

Pulls daily delivery reports from the Innovid API for all active advertisers and loads them to BigQuery. Handles Innovid's async report generation — request the report, receive a token, poll until the report is ready, download the zipped CSV, and load.

## How It Works

- Authenticates with Innovid's REST API using Basic Auth (base64 encoded credentials)
- Pulls the full client/advertiser hierarchy from the `/advertisers` endpoint
- Loops through every client and advertiser, requesting a daily delivery report for each
- Innovid returns a `reportStatusToken` — the report isn't ready yet, it's being generated
- Polls the status endpoint every 30 seconds until `reportStatus` is `READY` or `FAIL`
- When ready, downloads the report directly as a zipped CSV via the `reportUrl`
- Collects all advertiser reports into a single DataFrame using `pd.concat`
- Deletes the existing day's data from BigQuery before loading to ensure idempotency (DELETE + INSERT pattern)
- Loads the combined DataFrame to BigQuery in a single load job

## Key Patterns

- **Async polling loop** — `for attempt in range(30)` with `time.sleep(30)` gives Innovid up to 15 minutes per report. Breaks on READY or FAIL.
- **Idempotent loading** — deletes the target date's data before reloading so the script can be safely re-run without creating duplicates
- **Error handling** — try/except around both the report request and the BigQuery load. One failed advertiser doesn't kill the whole run (`continue` pattern)
- **In-memory collection** — all DataFrames held in RAM and concatenated at the end for a single BigQuery load job instead of one per advertiser
