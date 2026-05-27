from playwright.async_api import async_playwright
import asyncio
import json
import csv
import re

# List of team URLs to process
TEAM_RESULTS_URLS = [
    "https://www.livescore.com/en/football/team/real-madrid/4009/results/",
]

MAX_MATCHES = 10
HEADLESS = True  
MAX_WORKERS = 10


def get_team_name_from_url(url):
    """Extracts the team name from the livescore URL to use in filenames."""
    m = re.search(r"/team/([^/]+)/", url)
    return m.group(1).replace("-", "_") if m else "unknown_team"


def get_team_id_from_url(url):
    """Extracts numeric team id from a livescore team URL."""
    m = re.search(r"/team/[^/]+/(\d+)/", url)
    return m.group(1) if m else None


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_csv(path, rows):
    if not rows:
        print(f"No rows to save for {path}")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def get_match_id_from_url(url):
    m = re.search(r"/(\d+)/?$", url)
    return m.group(1) if m else None


def extract_pair(stat_value):
    if isinstance(stat_value, list) and len(stat_value) >= 2:
        return stat_value[0], stat_value[1]
    return None, None


def normalize_team_name(name):
    return (name or "").strip().lower()


def to_int_or_none(value):
    try:
        return int(value)
    except Exception:
        return None


def get_result_label(team_score, opponent_score):
    team_score_int = to_int_or_none(team_score)
    opponent_score_int = to_int_or_none(opponent_score)

    if team_score_int is None or opponent_score_int is None:
        return ""
    if team_score_int > opponent_score_int:
        return "W"
    if team_score_int < opponent_score_int:
        return "L"
    return "D"


def map_stat_for_team(stat_pair, is_home):
    home_val, away_val = extract_pair(stat_pair)
    if is_home:
        return home_val, away_val
    return away_val, home_val


def build_team_centric_stats_row(match_info, statistics, target_team_id=None, target_team_label=""):
    home_team_id = str(match_info.get("home_team_id") or "")
    away_team_id = str(match_info.get("away_team_id") or "")

    target_name_norm = normalize_team_name(target_team_label.replace("_", " "))
    home_name_norm = normalize_team_name(match_info.get("home_team"))
    away_name_norm = normalize_team_name(match_info.get("away_team"))

    if target_team_id and home_team_id == str(target_team_id):
        is_home = True
    elif target_team_id and away_team_id == str(target_team_id):
        is_home = False
    elif target_name_norm and target_name_norm == home_name_norm:
        is_home = True
    elif target_name_norm and target_name_norm == away_name_norm:
        is_home = False
    else:
        is_home = True

    team_name = match_info.get("home_team") if is_home else match_info.get("away_team")
    opponent_name = match_info.get("away_team") if is_home else match_info.get("home_team")
    team_score = match_info.get("home_score") if is_home else match_info.get("away_score")
    opponent_score = match_info.get("away_score") if is_home else match_info.get("home_score")

    shots_on_target_team, shots_on_target_opponent = map_stat_for_team(statistics.get("shotsOnTarget"), is_home)
    shots_off_target_team, shots_off_target_opponent = map_stat_for_team(statistics.get("shotsOffTarget"), is_home)
    shots_blocked_team, shots_blocked_opponent = map_stat_for_team(statistics.get("shotsBlocked"), is_home)
    corners_team, corners_opponent = map_stat_for_team(statistics.get("corners"), is_home)
    offsides_team, offsides_opponent = map_stat_for_team(statistics.get("offsides"), is_home)
    fouls_team, fouls_opponent = map_stat_for_team(statistics.get("fouls"), is_home)
    throw_ins_team, throw_ins_opponent = map_stat_for_team(statistics.get("throwIns"), is_home)
    yellow_cards_team, yellow_cards_opponent = map_stat_for_team(statistics.get("yellowCards"), is_home)
    yellow_red_cards_team, yellow_red_cards_opponent = map_stat_for_team(statistics.get("yellowRedCards"), is_home)
    red_cards_team, red_cards_opponent = map_stat_for_team(statistics.get("redCards"), is_home)
    crosses_team, crosses_opponent = map_stat_for_team(statistics.get("crosses"), is_home)
    goalkeeper_saves_team, goalkeeper_saves_opponent = map_stat_for_team(statistics.get("goalkeeperSaves"), is_home)
    goal_kicks_team, goal_kicks_opponent = map_stat_for_team(statistics.get("goalKicks"), is_home)

    return {
        "target_team": team_name,
        "opponent_team": opponent_name,
        "venue": "home" if is_home else "away",
        "team_score": team_score,
        "opponent_score": opponent_score,
        "result": get_result_label(team_score, opponent_score),
        "shots_on_target_team": shots_on_target_team,
        "shots_on_target_opponent": shots_on_target_opponent,
        "shots_off_target_team": shots_off_target_team,
        "shots_off_target_opponent": shots_off_target_opponent,
        "shots_blocked_team": shots_blocked_team,
        "shots_blocked_opponent": shots_blocked_opponent,
        "corners_team": corners_team,
        "corners_opponent": corners_opponent,
        "offsides_team": offsides_team,
        "offsides_opponent": offsides_opponent,
        "fouls_team": fouls_team,
        "fouls_opponent": fouls_opponent,
        "throw_ins_team": throw_ins_team,
        "throw_ins_opponent": throw_ins_opponent,
        "yellow_cards_team": yellow_cards_team,
        "yellow_cards_opponent": yellow_cards_opponent,
        "yellow_red_cards_team": yellow_red_cards_team,
        "yellow_red_cards_opponent": yellow_red_cards_opponent,
        "red_cards_team": red_cards_team,
        "red_cards_opponent": red_cards_opponent,
        "crosses_team": crosses_team,
        "crosses_opponent": crosses_opponent,
        "goalkeeper_saves_team": goalkeeper_saves_team,
        "goalkeeper_saves_opponent": goalkeeper_saves_opponent,
        "goal_kicks_team": goal_kicks_team,
        "goal_kicks_opponent": goal_kicks_opponent,
    }


async def dismiss_popups(page):
    possible_buttons = [
        "Accept",
        "I Agree",
        "AGREE",
        "Got it",
        "Continue",
    ]

    for text in possible_buttons:
        try:
            btn = page.get_by_text(text, exact=True)
            if await btn.count() > 0:
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(1000)
                # print(f"Clicked popup button: {text}") # Commented out to reduce console noise
                break
        except Exception:
            pass


def flatten_history(side_name, side_data, target_team):
    rows = []

    for group in side_data or []:
        stage_info = group.get("stage", {})
        events = group.get("events", [])

        for event in events:
            home_name = event.get("homeName", "")
            away_name = event.get("awayName", "")
            home_score = event.get("homeScore", "")
            away_score = event.get("awayScore", "")
            start_time = event.get("startDateTimeString", "")
            status_code = event.get("statusCode", "")

            if target_team == home_name:
                gf = safe_int(home_score)
                ga = safe_int(away_score)
                team_side = "home"
                opponent = away_name
            elif target_team == away_name:
                gf = safe_int(away_score)
                ga = safe_int(home_score)
                team_side = "away"
                opponent = home_name
            else:
                gf = None
                ga = None
                team_side = ""
                opponent = ""

            if gf is None or ga is None:
                result = ""
            elif gf > ga:
                result = "W"
            elif gf < ga:
                result = "L"
            else:
                result = "D"

            rows.append({
                "team_bucket": side_name,
                "target_team": target_team,
                "match_date": start_time,
                "competition_country": stage_info.get("countryName", ""),
                "competition_category": stage_info.get("category", ""),
                "competition_name": stage_info.get("stageName", ""),
                "is_cup": stage_info.get("isCup", False),
                "team_side": team_side,
                "opponent": opponent,
                "goals_for": gf,
                "goals_against": ga,
                "result": result,
                "status_code": status_code,
                "home_name": home_name,
                "away_name": away_name,
            })

    return rows


async def collect_recent_match_urls(page, team_url, max_matches=10):
    """
    Robustly collect recent finished match URLs from the top result cards.
    Extracts href directly from each card's outerHTML using regex.
    """
    await page.goto(team_url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(4000)
    await dismiss_popups(page)

    for _ in range(10):
        await page.mouse.wheel(0, 50)
        await page.wait_for_timeout(800)
        if await page.locator('div[data-id$="_mtc-r"]').count() >= max_matches:
            break

    urls = []
    seen = set()

    cards = page.locator('div[data-id$="_mtc-r"]')
    card_count = await cards.count()
    print(f"  -> Found {card_count} result cards on page")

    for i in range(card_count):
        try:
            card = cards.nth(i)

            outer_html = await card.evaluate("el => el.outerHTML")
            inner_text = (await card.inner_text()).strip().upper()

            # keep only finished matches
            if not any(x in inner_text for x in ["FT", "AET", "PEN"]):
                continue

            # extract first match URL from the card HTML
            m = re.search(r'href="([^"]*/en/football/[^"]*/\d+/?)"', outer_html)
            if not m:
                # fallback for relative href
                m = re.search(r'href="([^"]*/football/[^"]*/\d+/?)"', outer_html)

            if not m:
                continue

            href = m.group(1)

            if href.startswith("/"):
                full_url = "https://www.livescore.com" + href
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = "https://www.livescore.com/" + href.lstrip("/")

            if not re.search(r"/\d+/?$", full_url):
                continue

            if full_url in seen:
                continue

            seen.add(full_url)
            urls.append(full_url)

            if len(urls) >= max_matches:
                break

        except Exception as e:
            pass

    # full page HTML fallback
    if not urls:
        print("  -> Card-based extraction returned 0 URLs. Trying page HTML fallback...")
        html = await page.content()

        found = re.findall(r'href="(/en/football/[^"]*/\d+/)"', html)
        if not found:
            found = re.findall(r'href="(/football/[^"]*/\d+/)"', html)

        for href in found:
            full_url = "https://www.livescore.com" + href if href.startswith("/") else href

            if "/team/" in full_url or "/news/" in full_url or "/standings/" in full_url:
                continue

            if full_url in seen:
                continue

            seen.add(full_url)
            urls.append(full_url)

            if len(urls) >= max_matches:
                break

    return urls[:max_matches]


async def scrape_match_data(page, match_url, target_team_id=None, target_team_label=""):
    match_id = get_match_id_from_url(match_url)
    if not match_id:
        print(f"Skipping invalid match URL: {match_url}")
        return None

    captured = {
        "main_page_data": None,
        "stats_page_data": None,
        "h2h_page_data": None,
    }

    async def handle_response(response):
        try:
            url = response.url.lower()
            if "_next/data" not in url:
                return

            data = await response.json()

            if f"/{match_id}/stats.json" in url:
                captured["stats_page_data"] = data
            elif f"/{match_id}/h2h.json" in url:
                captured["h2h_page_data"] = data
            elif f"/{match_id}.json" in url or (f"/{match_id}/" in url and captured["main_page_data"] is None):
                if captured["main_page_data"] is None:
                    captured["main_page_data"] = data

        except Exception:
            pass

    page.on("response", handle_response)

    try:
        await page.goto(match_url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(3000)
        await dismiss_popups(page)

        try:
            stats_tab = page.get_by_text("Stats", exact=True)
            if await stats_tab.count() == 0:
                stats_tab = page.get_by_text("Statistics", exact=True)
            if await stats_tab.count() > 0:
                await stats_tab.first.click(timeout=3000)
                await page.wait_for_timeout(2500)
        except Exception:
            pass

        try:
            h2h_tab = page.get_by_text("H2H", exact=True)
            if await h2h_tab.count() > 0:
                await h2h_tab.first.click(timeout=3000)
                await page.wait_for_timeout(2500)
        except Exception:
            pass

        for suffix, key in [("stats/", "stats_page_data"), ("h2h/", "h2h_page_data")]:
            if captured[key] is not None:
                continue
            try:
                fallback_url = match_url.rstrip("/") + "/" + suffix
                await page.goto(fallback_url, wait_until="domcontentloaded", timeout=90000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass

    except Exception as e:
        print(f"Error scraping match {match_url}: {e}")

    finally:
        try:
            page.remove_listener("response", handle_response)
        except Exception:
            pass

    source_data = captured["stats_page_data"] or captured["h2h_page_data"] or captured["main_page_data"]
    if not source_data:
        print(f"[{match_id}] No usable JSON captured")
        return None

    try:
        event = source_data["pageProps"]["initialEventData"]["event"]
    except Exception:
        print(f"[{match_id}] Could not locate event data")
        return None

    match_info = {
        "match_id": event.get("id"),
        "match_url": match_url,
        "competition": event.get("competitionName"),
        "category": event.get("categoryName"),
        "stage": event.get("stageName"),
        "status": event.get("status"),
        "status_description": event.get("statusDescription"),
        "start_time": event.get("startDateTimeString"),
        "finish_time": event.get("finishDateTimeString"),
        "home_team": event.get("homeTeamName"),
        "away_team": event.get("awayTeamName"),
        "home_team_id": event.get("homeTeamId"),
        "away_team_id": event.get("awayTeamId"),
        "home_score": event.get("homeTeamScore"),
        "away_score": event.get("awayTeamScore"),
        "home_full_time_score": event.get("homeFullTimeScore"),
        "away_full_time_score": event.get("awayFullTimeScore"),
        "winner": event.get("winner"),
        "has_stats": event.get("hasStats"),
        "has_comments": event.get("hasComments"),
        "has_incidents": event.get("hasIncidents"),
        "has_media": event.get("hasMedia"),
    }

    home_form = event.get("homeScoreForm", [])
    away_form = event.get("awayScoreForm", [])
    head_to_head = event.get("headToHead", {})
    statistics = event.get("statistics", {})
    tabs = event.get("tabs", [])

    team_centric_stats_row = build_team_centric_stats_row(
        match_info,
        statistics,
        target_team_id=target_team_id,
        target_team_label=target_team_label,
    )

    history_rows = []
    history_rows.extend(flatten_history("home", head_to_head.get("home", []), match_info["home_team"]))
    history_rows.extend(flatten_history("away", head_to_head.get("away", []), match_info["away_team"]))

    output = {
        "match_info": match_info,
        "home_form": home_form,
        "away_form": away_form,
        "tabs": tabs,
        "statistics": team_centric_stats_row,
        "history": history_rows,
    }

    return output, team_centric_stats_row, history_rows


async def main():
    sem = asyncio.Semaphore(MAX_WORKERS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()

        for team_url in TEAM_RESULTS_URLS:
            team_name = get_team_name_from_url(team_url)
            team_id = get_team_id_from_url(team_url)
            print(f"\n{'='*50}")
            print(f"Processing Team: {team_name.upper()}")
            print(f"{'='*50}")

            listing_page = await context.new_page()
            match_urls = await collect_recent_match_urls(listing_page, team_url, MAX_MATCHES)
            await listing_page.close()

            print(f"  -> Collected {len(match_urls)} recent match URLs")

            if not match_urls:
                print(f"  -> No match URLs found for {team_name}. Skipping to next team.")
                continue

            all_stats_rows = []

            async def scrape_worker(match_url, idx):
                async with sem:
                    page = await context.new_page()
                    try:
                        print(f"    [Scraping {idx}/{len(match_urls)}] {match_url.split('/')[-2]}")
                        return await scrape_match_data(
                            page,
                            match_url,
                            target_team_id=team_id,
                            target_team_label=team_name,
                        )
                    except Exception as e:
                        print(f"    [Error] {match_url}: {e}")
                        return None
                    finally:
                        await page.close()

            tasks = [scrape_worker(url, idx) for idx, url in enumerate(match_urls, start=1)]
            results = await asyncio.gather(*tasks)

            for result in results:
                if not result:
                    continue
                
                # Unpack the results (ignoring output and history_rows as requested)
                output, stats_row, history_rows = result
                all_stats_rows.append(stats_row)

            # Define specific file name for this team's stats
            out_stats = f"{team_name}_stats.csv"

            # Save strictly the stats CSV
            save_csv(out_stats, all_stats_rows)

            print(f"\n  -> Finished {team_name.upper()}!")
            print(f"     Saved: {out_stats}")

        await browser.close()
    print("\nALL TEAMS PROCESSED SUCCESSFULLY.\n")


if __name__ == "__main__":
    asyncio.run(main())