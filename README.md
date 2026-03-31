# LiveScore CSV Scraper - Quick Start

## 🚀 Quick Setup (3 steps)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
python -m playwright install
```

### Step 2: Run Locally
```bash
python -m uvicorn app:app --reload
```

### Step 3: Open Browser
Visit `http://localhost:8000` and start scraping!

---

## 📦 Deploy to Heroku (3 commands)

```bash
heroku login
heroku create your-app-name
git push heroku main
```

Then open with: `heroku open`

---

## 📝 How to Use

1. **Paste URLs** or **Upload a file** with LiveScore team URLs (one per line)
2. Click **"Start Scraping"**
3. Wait for progress to complete
4. **Download CSV** files for each team

Example URL:
```
https://www.livescore.com/en/football/team/real-madrid/4009/results/
```

---

## 📚 Full Documentation

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Detailed local setup
- Heroku deployment guide
- API endpoints
- Troubleshooting
- CSV output format

---

## 🛠️ Project Files

- **app.py** - FastAPI backend with scraping engine
- **frontend.html** - Beautiful web interface
- **main.py** - Core scraping logic (unchanged)
- **requirements.txt** - All Python dependencies
- **Procfile** - Heroku deployment config
- **runtime.txt** - Python version (3.11.7)

---

## ⚡ What's New

✅ Web interface with real-time progress  
✅ Support for text input and file uploads  
✅ Parallel processing of multiple URLs  
✅ Separate CSV downloads for each team  
✅ Ready for Heroku deployment  
✅ Modern, responsive design  

Enjoy! 🎉
