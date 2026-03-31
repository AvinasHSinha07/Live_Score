from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import csv
import io
import os
import threading
import time
import uuid
import zipfile

from playwright.async_api import async_playwright

# Import scraping functions from main.py
from main import (
    abort_non_essential_assets,
    get_team_name_from_url,
    get_team_id_from_url,
    collect_recent_match_urls,
    scrape_match_data,
)

app = FastAPI(title="LiveScore CSV Scraper")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active jobs
jobs = {}
jobs_lock = threading.Lock()

MAX_MATCHES = int(os.environ.get("MAX_MATCHES", "10"))
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))
JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_SECONDS", "3600"))
BLOCK_NON_ESSENTIAL_ASSETS = os.environ.get("BLOCK_NON_ESSENTIAL_ASSETS", "true").lower() == "true"
EXTRA_MATCH_BUFFER = int(os.environ.get("EXTRA_MATCH_BUFFER", "6"))


def cleanup_finished_jobs():
    now = time.time()
    with jobs_lock:
        expired_job_ids = [
            job_id
            for job_id, job in jobs.items()
            if job.get("finished_at") and (now - job["finished_at"] > JOB_TTL_SECONDS)
        ]
        for job_id in expired_job_ids:
            jobs.pop(job_id, None)


def set_job_status(job_id, status, error_message=None):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job["status"] = status
        if error_message:
            job["error"] = error_message
        if status in {"completed", "failed"}:
            job["finished_at"] = time.time()


def to_int_or_none(value):
    try:
        return int(value)
    except Exception:
        return None


def avg(values):
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)


def pct(numerator, denominator):
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def build_team_analysis(rows):
    total = len(rows)
    if total == 0:
        return {
            "sample_size": 0,
            "summary": "No completed matches available for analysis.",
            "markets": {},
            "averages": {},
            "risk_note": "Insufficient data sample.",
        }

    valid_goals = [r for r in rows if to_int_or_none(r.get("team_score")) is not None and to_int_or_none(r.get("opponent_score")) is not None]
    total_goals_matches = len(valid_goals)
    
    if total_goals_matches == 0:
         return {
            "sample_size": total,
            "summary": "No completed matches available for analysis.",
            "markets": {},
            "averages": {},
            "risk_note": "Insufficient match data.",
        }

    markets = {}
    averages = {}

    def get_val(r, key):
        return to_int_or_none(r.get(key))

    # Calculate Markets Hit Rates
    markets['Win Match'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') > get_val(r, 'opponent_score')), total_goals_matches)
    markets['Draw Match'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') == get_val(r, 'opponent_score')), total_goals_matches)
    markets['Lose Match'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') < get_val(r, 'opponent_score')), total_goals_matches)
    markets['Clean Sheet (Team Concedes 0)'] = pct(sum(1 for r in valid_goals if get_val(r, 'opponent_score') == 0), total_goals_matches)
    markets['Failed to Score (Team Scores 0)'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') == 0), total_goals_matches)

    markets['Over 1.5 Match Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') + get_val(r, 'opponent_score') >= 2), total_goals_matches)
    markets['Over 2.5 Match Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') + get_val(r, 'opponent_score') >= 3), total_goals_matches)
    markets['Over 3.5 Match Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') + get_val(r, 'opponent_score') >= 4), total_goals_matches)
    markets['Both Teams To Score (BTTS - YES)'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') > 0 and get_val(r, 'opponent_score') > 0), total_goals_matches)

    markets['Team Over 0.5 Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') >= 1), total_goals_matches)
    markets['Team Over 1.5 Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') >= 2), total_goals_matches)
    markets['Team Over 2.5 Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'team_score') >= 3), total_goals_matches)
    markets['Opponent Over 0.5 Goals'] = pct(sum(1 for r in valid_goals if get_val(r, 'opponent_score') >= 1), total_goals_matches)

    markets['Win & Over 1.5 Goals'] = pct(sum(1 for r in valid_goals if (get_val(r, 'team_score') > get_val(r, 'opponent_score')) and (get_val(r, 'team_score') + get_val(r, 'opponent_score') >= 2)), total_goals_matches)
    markets['Win & BTTS (Yes)'] = pct(sum(1 for r in valid_goals if (get_val(r, 'team_score') > get_val(r, 'opponent_score')) and (get_val(r, 'team_score') > 0 and get_val(r, 'opponent_score') > 0)), total_goals_matches)

    # Corners
    valid_corners = [r for r in rows if get_val(r, 'corners_team') is not None and get_val(r, 'corners_opponent') is not None]
    if len(valid_corners) > 0:
        c_matches = len(valid_corners)
        markets['Over 7.5 Match Corners'] = pct(sum(1 for r in valid_corners if get_val(r, 'corners_team') + get_val(r, 'corners_opponent') >= 8), c_matches)
        markets['Over 9.5 Match Corners'] = pct(sum(1 for r in valid_corners if get_val(r, 'corners_team') + get_val(r, 'corners_opponent') >= 10), c_matches)
        markets['Team Over 4.5 Corners'] = pct(sum(1 for r in valid_corners if get_val(r, 'corners_team') >= 5), c_matches)
        markets['Team Wins Corner Matchup'] = pct(sum(1 for r in valid_corners if get_val(r, 'corners_team') > get_val(r, 'corners_opponent')), c_matches)

    # Yellow Cards
    valid_cards = [r for r in rows if get_val(r, 'yellow_cards_team') is not None and get_val(r, 'yellow_cards_opponent') is not None]
    if len(valid_cards) > 0:
        y_matches = len(valid_cards)
        markets['Over 2.5 Match Yellow Cards'] = pct(sum(1 for r in valid_cards if get_val(r, 'yellow_cards_team') + get_val(r, 'yellow_cards_opponent') >= 3), y_matches)
        markets['Over 3.5 Match Yellow Cards'] = pct(sum(1 for r in valid_cards if get_val(r, 'yellow_cards_team') + get_val(r, 'yellow_cards_opponent') >= 4), y_matches)
        markets['Team Over 1.5 Yellow Cards'] = pct(sum(1 for r in valid_cards if get_val(r, 'yellow_cards_team') >= 2), y_matches)
        markets['Opponent Over 1.5 Yellow Cards'] = pct(sum(1 for r in valid_cards if get_val(r, 'yellow_cards_opponent') >= 2), y_matches)

    # Shots on Target
    valid_sot = [r for r in rows if get_val(r, 'shots_on_target_team') is not None and get_val(r, 'shots_on_target_opponent') is not None]
    if len(valid_sot) > 0:
        s_matches = len(valid_sot)
        markets['Team Over 3.5 Shots on Target'] = pct(sum(1 for r in valid_sot if get_val(r, 'shots_on_target_team') >= 4), s_matches)
        markets['Team Over 5.5 Shots on Target'] = pct(sum(1 for r in valid_sot if get_val(r, 'shots_on_target_team') >= 6), s_matches)
        markets['Opponent Over 2.5 Shots on Target'] = pct(sum(1 for r in valid_sot if get_val(r, 'shots_on_target_opponent') >= 3), s_matches)

    # Averages
    team_goals = [get_val(r, 'team_score') for r in valid_goals]
    opp_goals = [get_val(r, 'opponent_score') for r in valid_goals]
    
    averages['Goals Scored'] = avg(team_goals)
    averages['Goals Conceded'] = avg(opp_goals)
    averages['Total Match Goals'] = avg([tg + og for tg, og in zip(team_goals, opp_goals)])

    if valid_corners:
        t_corn = [get_val(r, 'corners_team') for r in valid_corners]
        o_corn = [get_val(r, 'corners_opponent') for r in valid_corners]
        averages['Team Corners'] = avg(t_corn)
        averages['Opponent Corners'] = avg(o_corn)
        averages['Total Match Corners'] = avg([t + o for t, o in zip(t_corn, o_corn)])

    if valid_sot:
        t_sot = [get_val(r, 'shots_on_target_team') for r in valid_sot]
        o_sot = [get_val(r, 'shots_on_target_opponent') for r in valid_sot]
        averages['Team Shots on Target'] = avg(t_sot)
        averages['Opponent SOT Allowed'] = avg(o_sot)

    if valid_cards:
        t_y = [get_val(r, 'yellow_cards_team') for r in valid_cards]
        o_y = [get_val(r, 'yellow_cards_opponent') for r in valid_cards]
        averages['Team Yellow Cards'] = avg(t_y)
        averages['Opponent Yellow Cards'] = avg(o_y)

    valid_fouls = [r for r in rows if get_val(r, 'fouls_team') is not None]
    if valid_fouls:
        averages['Team Fouls Committed'] = avg([get_val(r, 'fouls_team') for r in valid_fouls])

    valid_offsides = [r for r in rows if get_val(r, 'offsides_team') is not None]
    if valid_offsides:
        averages['Team Offsides'] = avg([get_val(r, 'offsides_team') for r in valid_offsides])

    valid_thi = [r for r in rows if get_val(r, 'throw_ins_team') is not None and get_val(r, 'throw_ins_opponent') is not None]
    if valid_thi:
        averages['Total Match Throw-ins'] = avg([get_val(r, 'throw_ins_team') + get_val(r, 'throw_ins_opponent') for r in valid_thi])

    valid_gk = [r for r in rows if get_val(r, 'goal_kicks_team') is not None and get_val(r, 'goal_kicks_opponent') is not None]
    if valid_gk:
        averages['Total Match Goal Kicks'] = avg([get_val(r, 'goal_kicks_team') + get_val(r, 'goal_kicks_opponent') for r in valid_gk])

    return {
        "sample_size": total,
        "markets": markets,
        "averages": averages,
    }


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML"""
    with open("frontend.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/scrape")
async def scrape_urls(urls: dict):
    """
    Scrape URLs and return CSV data
    
    Expected format:
    {
        "urls": ["url1", "url2", ...]
    }
    """
    cleanup_finished_jobs()

    url_list = urls.get("urls", [])
    
    if not url_list:
        raise HTTPException(status_code=400, detail="No URLs provided")
    
    # Validate URLs
    url_list = [url.strip() for url in url_list if url.strip()]
    
    if not url_list:
        raise HTTPException(status_code=400, detail="No valid URLs provided")
    
    # Create job ID
    job_id = f"job_{uuid.uuid4().hex}"

    with jobs_lock:
        jobs[job_id] = {
            "status": "processing",
            "results": {},
            "analyses": {},
            "errors": {},
            "progress": 0,
            "total": len(url_list),
            "started_at": time.time(),
        }

    # Run scraping in an isolated thread that owns its own event loop
    asyncio.create_task(asyncio.to_thread(run_job_in_thread, job_id, url_list))
    
    return {"job_id": job_id, "status": "processing", "total_urls": len(url_list)}


def run_job_in_thread(job_id: str, url_list: list):
    # Uvicorn reload on Windows may force Selector loops. Playwright needs Proactor
    # for subprocess creation, so each worker job runs in its own Proactor loop.
    if os.name == "nt" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_urls_async(job_id, url_list))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


async def process_urls_async(job_id: str, url_list: list):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context()

            if BLOCK_NON_ESSENTIAL_ASSETS:
                await context.route("**/*", abort_non_essential_assets)

            page_sem = asyncio.Semaphore(MAX_WORKERS)
            team_sem = asyncio.Semaphore(min(max(1, len(url_list)), MAX_WORKERS))

            async def process_team(team_url: str):
                team_name = get_team_name_from_url(team_url)
                team_id = get_team_id_from_url(team_url)

                try:
                    listing_page = await context.new_page()
                    try:
                        candidate_limit = max(MAX_MATCHES, MAX_MATCHES + max(0, EXTRA_MATCH_BUFFER))
                        match_urls = await collect_recent_match_urls(
                            listing_page,
                            team_url,
                            candidate_limit,
                        )
                    finally:
                        await listing_page.close()

                    if not match_urls:
                        with jobs_lock:
                            job = jobs.get(job_id)
                            if job:
                                job["errors"][team_name] = "No match URLs found"
                                job["progress"] += 1
                        return

                    async def scrape_single_match(match_url: str):
                        async with page_sem:
                            page = await context.new_page()
                            try:
                                return await scrape_match_data(
                                    page,
                                    match_url,
                                    target_team_id=team_id,
                                    target_team_label=team_name,
                                )
                            except Exception:
                                return None
                            finally:
                                await page.close()

                    primary_urls = match_urls[:MAX_MATCHES]
                    extra_urls = match_urls[MAX_MATCHES:]

                    primary_results = await asyncio.gather(*(scrape_single_match(url) for url in primary_urls))
                    ordered_primary_rows = []
                    missing_detailed_count = 0

                    for result in primary_results:
                        if not result:
                            continue
                        _, stats_row, _, has_detailed_stats = result
                        ordered_primary_rows.append({
                            "row": stats_row,
                            "has_detailed_stats": has_detailed_stats,
                        })
                        if not has_detailed_stats:
                            missing_detailed_count += 1

                    replacement_rows = []
                    if missing_detailed_count > 0:
                        for url in extra_urls:
                            extra_result = await scrape_single_match(url)
                            if not extra_result:
                                continue

                            _, stats_row, _, has_detailed_stats = extra_result
                            if has_detailed_stats:
                                replacement_rows.append(stats_row)

                            if len(replacement_rows) >= missing_detailed_count:
                                break

                    replacement_idx = 0
                    all_stats_rows = []
                    for item in ordered_primary_rows:
                        if item["has_detailed_stats"]:
                            all_stats_rows.append(item["row"])
                            continue

                        if replacement_idx < len(replacement_rows):
                            all_stats_rows.append(replacement_rows[replacement_idx])
                            replacement_idx += 1
                        else:
                            all_stats_rows.append(item["row"])

                    all_stats_rows = all_stats_rows[:MAX_MATCHES]

                    with jobs_lock:
                        job = jobs.get(job_id)
                        if job:
                            job["results"][team_name] = all_stats_rows
                            job["analyses"][team_name] = build_team_analysis(all_stats_rows)
                            job["progress"] += 1

                except Exception as exc:
                    with jobs_lock:
                        job = jobs.get(job_id)
                        if job:
                            job["errors"][team_name] = str(exc)
                            job["progress"] += 1

            async def team_runner(team_url: str):
                async with team_sem:
                    await process_team(team_url)

            await asyncio.gather(*(team_runner(url) for url in url_list))
            await context.close()
            await browser.close()

        set_job_status(job_id, "completed")

    except Exception as exc:
        set_job_status(job_id, "failed", str(exc))



@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and results"""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        response = {
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
            "total": job["total"],
            "completed_urls": len(job["results"]),
            "failed_urls": len(job["errors"]),
            "results": dict(job["results"]),
            "analyses": dict(job.get("analyses", {})),
            "errors": dict(job["errors"]),
        }

        if "error" in job:
            response["error"] = job["error"]

    return response


@app.get("/api/download/{job_id}/{team_name}")
async def download_csv(job_id: str, team_name: str):
    """Download CSV for a specific team"""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if team_name not in job["results"]:
            raise HTTPException(status_code=404, detail="Team data not found")
        rows = list(job["results"][team_name])
    
    # Create CSV in memory
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    
    # Convert to bytes
    csv_bytes = output.getvalue().encode("utf-8-sig")
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={team_name}_stats.csv"}
    )


@app.get("/api/download-all/{job_id}")
async def download_all_csvs(job_id: str):
    """Download all team CSV files in a single ZIP archive."""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        team_results = dict(job["results"])

    if not team_results:
        raise HTTPException(status_code=404, detail="No CSV data available for this job")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for team_name, rows in team_results.items():
            csv_buffer = io.StringIO()
            if rows:
                writer = csv.DictWriter(csv_buffer, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            zf.writestr(f"{team_name}_stats.csv", csv_buffer.getvalue().encode("utf-8-sig"))

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={job_id}_csv_bundle.zip"},
    )





if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
