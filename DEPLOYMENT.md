# LiveScore CSV Scraper - Deployment Guide

This project is best deployed for free using Hugging Face Spaces (Docker), because it supports FastAPI + Playwright in a single service.

## Recommended Free Hosting

- Platform: Hugging Face Spaces (Docker)
- Cost: Free tier available
- URL: Public HTTPS URL included
- Stack support: Python + Playwright + FastAPI

## What Was Added For Deployment

- `Dockerfile` for containerized startup
- `.dockerignore` to reduce image build context

## 1. Local Smoke Test (Before Deploy)

```bash
pip install -r requirements.txt
python -m playwright install
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` and test with one team URL first.

## 2. Deploy To Hugging Face Spaces (Free)

1. Push this project to GitHub.
2. Go to https://huggingface.co/new-space.
3. Create a Space:
   - Space SDK: `Docker`
   - Visibility: Public or Private
4. Connect/select your GitHub repository.
5. Space builds automatically using the existing `Dockerfile`.
6. After build completes, open your Space URL and use the app.

## 3. Recommended Environment Variables

In Space settings, add these variables:

- `HEADLESS=true`
- `MAX_MATCHES=8`
- `MAX_WORKERS=4`
- `BLOCK_NON_ESSENTIAL_ASSETS=true`
- `NAVIGATION_TIMEOUT_MS=45000`

These settings are a good balance for free-tier CPU/RAM.

## 4. Speed Tips For Free Tier

1. Keep `MAX_MATCHES` between 5 and 10.
2. Keep `MAX_WORKERS` between 3 and 5 on free CPU.
3. Use fewer team URLs per run for more stable completion.
4. Keep `BLOCK_NON_ESSENTIAL_ASSETS=true`.

## 5. API Endpoints

- `GET /` - frontend
- `POST /api/scrape` - start scraping job
- `GET /api/job/{job_id}` - job progress/results
- `GET /api/download/{job_id}/{team_name}` - single CSV
- `GET /api/download-all/{job_id}` - ZIP of all team CSVs

## 6. Troubleshooting

### Build fails

- Confirm `Dockerfile` is in repository root.
- Confirm `requirements.txt` exists and has valid versions.

### App is slow or restarts

- Lower `MAX_WORKERS` to `3`.
- Lower `MAX_MATCHES` to `5`.

### No match data

- Verify URL format includes `/team/<name>/<id>/results/`.
- Try another team with recent finished matches.

## Notes

- Free services can sleep after inactivity.
- For always-on and faster sustained throughput, paid tiers are required.
