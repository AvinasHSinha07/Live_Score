# LiveScore CSV Scraper - Deployment Guide

A web application for scraping football match statistics from LiveScore and exporting to CSV files.

## Features

- 🌐 Web interface for uploading URLs
- 📥 Support for text input and file uploads
- 📊 Parallel processing of multiple URLs
- 💾 Separate CSV downloads for each team
- ⚡ Real-time progress tracking
- 🎨 Modern, responsive UI

## Project Structure

```
├── main.py              # Original scraping logic
├── app.py               # FastAPI backend
├── frontend.html        # Web interface
├── requirements.txt     # Python dependencies
├── Procfile            # Heroku deployment config
├── runtime.txt         # Python version for Heroku
└── .gitignore          # Git ignore patterns
```

## Local Testing

### Prerequisites
- Python 3.11+
- pip

### Setup

1. **Clone/Extract the project**
   ```bash
   cd your-project-directory
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   python -m playwright install
   ```

4. **Run locally**
   ```bash
   python -m uvicorn app:app --reload
   ```

5. **Access the app**
   - Open `http://localhost:8000` in your browser

## Deployment to Heroku

### Prerequisites
- Heroku account (free tier works)
- Heroku CLI installed ([download](https://devcenter.heroku.com/articles/heroku-cli))
- Git installed

### Deployment Steps

1. **Login to Heroku**
   ```bash
   heroku login
   ```

2. **Create a new Heroku app**
   ```bash
   heroku create your-app-name
   ```

3. **Initialize Git (if not already done)**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

4. **Deploy to Heroku**
   ```bash
   git push heroku main
   # or if your branch is 'master':
   git push heroku master
   ```

5. **View logs**
   ```bash
   heroku logs --tail
   ```

6. **Open your app**
   ```bash
   heroku open
   ```

### Heroku Buildpacks (if needed)

If the app doesn't work, you may need to add buildpacks:

```bash
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-python
```

## Usage Guide

### Via Web Interface

1. **Enter URLs** - Two methods:
   - **Paste URLs**: Paste LiveScore team result URLs (one per line) in the text area
   - **Upload File**: Upload a `.txt` or `.csv` file with one URL per line

2. **Start Scraping** - Click "Start Scraping" button

3. **Monitor Progress** - Watch the progress bar as URLs are processed

4. **Download CSVs** - Once complete, download individual CSV files for each team

### Example URLs
```
https://www.livescore.com/en/football/team/real-madrid/4009/results/
https://www.livescore.com/en/football/team/manchester-city/6599/results/
https://www.livescore.com/en/football/team/fc-barcelona/122/results/
```

## CSV Output Format

Each downloaded CSV contains the following columns for each match:

- `target_team` - Team name
- `opponent_team` - Opposing team
- `venue` - Home or Away
- `team_score` - Team's score
- `opponent_score` - Opponent's score
- `result` - W/L/D (Win/Loss/Draw)
- `shots_on_target_team` / `shots_on_target_opponent`
- `shots_off_target_team` / `shots_off_target_opponent`
- `shots_blocked_team` / `shots_blocked_opponent`
- `corners_team` / `corners_opponent`
- `offsides_team` / `offsides_opponent`
- `fouls_team` / `fouls_opponent`
- `throw_ins_team` / `throw_ins_opponent`
- `yellow_cards_team` / `yellow_cards_opponent`
- `yellow_red_cards_team` / `yellow_red_cards_opponent`
- `red_cards_team` / `red_cards_opponent`
- `crosses_team` / `crosses_opponent`
- `goalkeeper_saves_team` / `goalkeeper_saves_opponent`
- `goal_kicks_team` / `goal_kicks_opponent`

## API Endpoints

### `GET /`
Returns the web interface (frontend.html)

### `POST /api/scrape`
Start a scraping job
- **Body**: `{"urls": ["url1", "url2", ...]}`
- **Response**: `{"job_id": "job_xxx", "status": "processing", "total_urls": n}`

### `GET /api/job/{job_id}`
Get job status and progress
- **Response**: Job details including progress, errors, and completed results

### `GET /api/download/{job_id}/{team_name}`
Download CSV for a specific team
- **Response**: CSV file download

## Troubleshooting

### Common Issues

**Issue: "No match URLs found"**
- The URL might not have any finished matches
- Try with a different team URL

**Issue: Scraper times out**
- Heroku free tier has memory constraints
- Reduce `MAX_MATCHES` in `app.py` to 5

**Issue: Heroku dyno crashes**
- Check logs: `heroku logs --tail`
- Free tier sleeps after 30 minutes of inactivity
- Consider upgrading to a Hobby dyno

**Issue: Playwright issues**
- The Procfile includes `playwright install` to download browsers
- This runs on first deployment

### Performance Tips

1. **Reduce workers** - Lower `MAX_WORKERS` in `app.py` if memory is limited
2. **Reduce matches** - Lower `MAX_MATCHES` for faster processing
3. **Use paid Heroku tier** - Free tier has 512MB RAM, may be insufficient

## Environment Variables (Optional)

You can set environment variables in Heroku:

```bash
heroku config:set MAX_MATCHES=5
heroku config:set MAX_WORKERS=5
```

Then update `app.py` to read from environment:
```python
MAX_MATCHES = int(os.environ.get("MAX_MATCHES", 10))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 10))
```

## License

This project uses Playwright for web scraping. Please ensure you have the rights to scrape the target websites.

## Support

For issues or questions, check:
1. The Heroku logs: `heroku logs --tail`
2. Browser console for frontend errors (F12)
3. The original `main.py` for scraping logic details
