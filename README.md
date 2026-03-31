# LiveScore CSV Scraper

FastAPI + Playwright app that scrapes recent LiveScore team matches and exports team stats CSV files from a web UI.

## Run Locally

1. Install dependencies:

```bash
pip install -r requirements.txt
python -m playwright install
```

2. Start server:

```bash
python -m uvicorn app:app --reload
```

3. Open:

http://localhost:8000

## Free Deployment (Recommended)

The project now includes a Docker setup for free hosting on Hugging Face Spaces (Docker), which supports Playwright.

Files added for deployment:

- `Dockerfile`
- `.dockerignore`

Full steps are in [DEPLOYMENT.md](DEPLOYMENT.md).

## Main Features

- URL paste or file upload input
- Multi-team scraping jobs
- Real-time progress polling
- Per-team CSV download and ZIP download
- Toggleable analysis panel and organized table view in frontend

## Runtime Tuning (Environment Variables)

- `MAX_MATCHES` (default `10`)
- `MAX_WORKERS` (default `10` in app, `6` in Docker env)
- `HEADLESS` (default `true`)
- `BLOCK_NON_ESSENTIAL_ASSETS` (default `true`)
- `NAVIGATION_TIMEOUT_MS` (default `45000`)

## Notes

- Free tiers may sleep when idle.
- Higher worker counts can speed up scraping but may increase memory/CPU usage.
