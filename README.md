# CTV Attribution Pipeline

Pulls daily vendor delivery files from S3, splits them into spend and attribution tables, and loads them into BigQuery with an atomic promote so dashboards never read half-loaded data.

## How it works

1. **Pull** — grabs the newest export from the S3 bucket.
2. **Split** — one vendor file holds two datasets. Rows with an Attribution_Window are attribution; rows without one are spend.
3. **Stage** — each split loads into a staging table (WRITE_TRUNCATE, wiped every run). A failure here touches nothing real.
4. **Promote** — a single BigQuery transaction deletes the file's date window from the final table and inserts the staged rows. Both happen or neither does.
5. **Serve** — a unified view joins spend and attribution for the frontend. It only refreshes after both promotes commit.

## Design decisions

- **Staging then promote:** loads can fail harmlessly; the final table only ever exists fully old or fully new.
- **DELETE + INSERT in one transaction:** reruns are idempotent. Crash and rerun the same file — the window gets wiped and refilled, no duplicates.
- **Split on nullability:** the vendor ships one mixed file. Attribution_Window IS NULL is the cleanest signal separating delivery rows from attribution rows.
- **Serving view last:** the frontend never reads raw loads, only a view that refreshes after promotion succeeds.
