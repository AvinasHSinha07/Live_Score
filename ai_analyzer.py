import asyncio
import json
import os
import traceback
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_num(value) -> Optional[float]:
    """Convert a value to float, returning None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg(values: List[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)


def _build_data_summary(team_name: str, rows: List[Dict[str, Any]]) -> str:
    """
    Build a concise textual summary of the scraped match data that will
    be injected into the Gemini prompt.
    """
    if not rows:
        return "No match data available."

    lines: List[str] = []
    lines.append(f"Team: {team_name}")
    lines.append(f"Matches analyzed: {len(rows)}")
    lines.append("")

    # --- match-by-match table ---
    lines.append("MATCH-BY-MATCH DATA:")
    lines.append(
        f"{'#':<3} {'Opponent':<22} {'Venue':<6} {'Score':<7} {'Res':<4} "
        f"{'SOT':<5} {'SOT-O':<6} {'Corn':<5} {'Corn-O':<7} "
        f"{'YC':<4} {'YC-O':<5} {'Fouls':<6} {'Fouls-O':<8}"
    )
    lines.append("-" * 110)

    for i, r in enumerate(rows, 1):
        opp = str(r.get("opponent_team", ""))[:20]
        venue = str(r.get("venue", ""))
        ts = r.get("team_score", "?")
        os_ = r.get("opponent_score", "?")
        res = r.get("result", "?")

        sot = r.get("shots_on_target_team", "?")
        sot_o = r.get("shots_on_target_opponent", "?")
        corn = r.get("corners_team", "?")
        corn_o = r.get("corners_opponent", "?")
        yc = r.get("yellow_cards_team", "?")
        yc_o = r.get("yellow_cards_opponent", "?")
        fouls = r.get("fouls_team", "?")
        fouls_o = r.get("fouls_opponent", "?")

        lines.append(
            f"{i:<3} {opp:<22} {venue:<6} {ts}-{os_:<5} {res:<4} "
            f"{sot:<5} {sot_o:<6} {corn:<5} {corn_o:<7} "
            f"{yc:<4} {yc_o:<5} {fouls:<6} {fouls_o:<8}"
        )

    # --- computed averages ---
    lines.append("")
    lines.append("COMPUTED AVERAGES:")

    team_goals = [_safe_num(r.get("team_score")) for r in rows]
    opp_goals = [_safe_num(r.get("opponent_score")) for r in rows]
    sot_vals = [_safe_num(r.get("shots_on_target_team")) for r in rows]
    sot_opp = [_safe_num(r.get("shots_on_target_opponent")) for r in rows]
    corn_vals = [_safe_num(r.get("corners_team")) for r in rows]
    corn_opp = [_safe_num(r.get("corners_opponent")) for r in rows]
    yc_vals = [_safe_num(r.get("yellow_cards_team")) for r in rows]
    yc_opp_vals = [_safe_num(r.get("yellow_cards_opponent")) for r in rows]
    fouls_vals = [_safe_num(r.get("fouls_team")) for r in rows]

    valid_goals = [(t, o) for t, o in zip(team_goals, opp_goals) if t is not None and o is not None]
    wins = sum(1 for t, o in valid_goals if t > o)
    draws = sum(1 for t, o in valid_goals if t == o)
    losses = sum(1 for t, o in valid_goals if t < o)
    total_valid = len(valid_goals)

    lines.append(f"  Record: {wins}W {draws}D {losses}L (out of {total_valid} completed)")
    lines.append(f"  Goals Scored Avg: {_avg(team_goals)}")
    lines.append(f"  Goals Conceded Avg: {_avg(opp_goals)}")
    total_match_goals = [t + o for t, o in valid_goals]
    lines.append(f"  Total Match Goals Avg: {_avg(total_match_goals)}")
    lines.append(f"  Shots on Target Avg: {_avg(sot_vals)}")
    lines.append(f"  Opponent SOT Avg: {_avg(sot_opp)}")
    lines.append(f"  Corners Avg: {_avg(corn_vals)}")
    lines.append(f"  Opponent Corners Avg: {_avg(corn_opp)}")
    lines.append(f"  Yellow Cards Avg: {_avg(yc_vals)}")
    lines.append(f"  Opponent Yellow Cards Avg: {_avg(yc_opp_vals)}")
    lines.append(f"  Fouls Avg: {_avg(fouls_vals)}")

    # --- hit rates ---
    if total_valid > 0:
        lines.append("")
        lines.append("HIT RATES:")
        btts = sum(1 for t, o in valid_goals if t > 0 and o > 0)
        o15 = sum(1 for t, o in valid_goals if t + o >= 2)
        o25 = sum(1 for t, o in valid_goals if t + o >= 3)
        o35 = sum(1 for t, o in valid_goals if t + o >= 4)
        cs = sum(1 for t, o in valid_goals if o == 0)

        lines.append(f"  Win: {wins}/{total_valid} ({round(wins/total_valid*100, 1)}%)")
        lines.append(f"  Over 1.5 Goals: {o15}/{total_valid} ({round(o15/total_valid*100, 1)}%)")
        lines.append(f"  Over 2.5 Goals: {o25}/{total_valid} ({round(o25/total_valid*100, 1)}%)")
        lines.append(f"  Over 3.5 Goals: {o35}/{total_valid} ({round(o35/total_valid*100, 1)}%)")
        lines.append(f"  BTTS Yes: {btts}/{total_valid} ({round(btts/total_valid*100, 1)}%)")
        lines.append(f"  Clean Sheet: {cs}/{total_valid} ({round(cs/total_valid*100, 1)}%)")

        # Corners hit rates
        valid_corn = [(c, co) for c, co in zip(corn_vals, corn_opp) if c is not None and co is not None]
        if valid_corn:
            tc = len(valid_corn)
            o85c = sum(1 for c, co in valid_corn if c + co >= 9)
            o95c = sum(1 for c, co in valid_corn if c + co >= 10)
            t45c = sum(1 for c, _ in valid_corn if c >= 5)
            lines.append(f"  Over 8.5 Corners: {o85c}/{tc} ({round(o85c/tc*100, 1)}%)")
            lines.append(f"  Over 9.5 Corners: {o95c}/{tc} ({round(o95c/tc*100, 1)}%)")
            lines.append(f"  Team Over 4.5 Corners: {t45c}/{tc} ({round(t45c/tc*100, 1)}%)")

        # Cards hit rates
        valid_yc = [(y, yo) for y, yo in zip(yc_vals, yc_opp_vals) if y is not None and yo is not None]
        if valid_yc:
            tyc = len(valid_yc)
            o25yc = sum(1 for y, yo in valid_yc if y + yo >= 3)
            o35yc = sum(1 for y, yo in valid_yc if y + yo >= 4)
            lines.append(f"  Over 2.5 Yellow Cards: {o25yc}/{tyc} ({round(o25yc/tyc*100, 1)}%)")
            lines.append(f"  Over 3.5 Yellow Cards: {o35yc}/{tyc} ({round(o35yc/tyc*100, 1)}%)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a professional football (soccer) betting analyst. You receive raw match \
statistics for a team's recent matches and must produce a clear, actionable \
betting analysis.

Your analysis MUST follow this exact structure with these markdown headers:

## 📊 Overview
A 2-3 sentence summary of the team's recent form, strengths, and weaknesses.

## ✅ Strong Bets (High Confidence)
List the betting markets with the HIGHEST probability of hitting based on the data. \
For each, give the market name, your confidence (%), and a one-line reasoning. \
Format each as a bullet point: `- **Market Name** (Confidence: XX%) — Reasoning`

## 🔄 Lean Bets (Moderate Confidence)
Markets that look favorable but with less certainty. Same format as above.

## ❌ Markets to Avoid
Markets that the data suggests will NOT hit. Explain why briefly.

## 🔢 Expected Goals Model
Give your expected goals estimate for the team and a typical opponent based on \
the data: `Team xG: X.XX | Opponent xG: X.XX | Predicted Total: X.XX`

## ⚽ Goals Markets Breakdown
Analyze Over/Under lines (1.5, 2.5, 3.5) and BTTS with probabilities.

## 🏁 Corners & Cards Insights
Analyze corner and card markets if data is available.

## ⚠️ Risk Notes
Any caveats: small sample size, recent form swings, home/away splits, etc.

RULES:
- Be specific. Use exact numbers from the data.
- Give confidence percentages for each recommendation.
- Consider recency: weight recent matches more.
- If sample is < 5 matches, explicitly warn about reliability.
- Never guarantee outcomes. Use probabilistic language.
- Keep the total response under 800 words.
"""


def _build_user_prompt(data_summary: str) -> str:
    return (
        f"Analyze the following team's recent match data and provide a complete "
        f"betting analysis following the required structure:\n\n"
        f"```\n{data_summary}\n```\n\n"
        f"Provide your full analysis now."
    )


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

async def analyze_team_with_ai(
    team_name: str,
    rows: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """
    Send scraped match data to Google Gemini and return an analysis dict.

    Returns
    -------
    dict with keys:
        ai_analysis  : str   – The full markdown analysis text
        model_used   : str   – Which Gemini model was used
        error        : str | None – Error message if the call failed
    """
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not resolved_key:
        return {
            "ai_analysis": None,
            "model_used": None,
            "error": "No Gemini API key configured.",
        }

    try:
        client = genai.Client(api_key=resolved_key)

        data_summary = _build_data_summary(team_name, rows)
        user_prompt = _build_user_prompt(data_summary)

        # Build list of fallback models to try if the main one is overloaded/unavailable
        fallback_models = [model]
        if model != "gemini-2.5-flash":
            fallback_models.append("gemini-2.5-flash")
        if "gemini-2.0-flash" not in fallback_models:
            fallback_models.append("gemini-2.0-flash")

        last_error = None
        successful_model = None
        response = None

        for current_model in fallback_models:
            retries = 3
            backoff = 1.0  # seconds
            
            for attempt in range(retries):
                try:
                    response = await client.aio.models.generate_content(
                        model=current_model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.4,
                            max_output_tokens=2048,
                        ),
                    )
                    successful_model = current_model
                    break
                except Exception as exc:
                    last_error = exc
                    exc_str = str(exc).lower()
                    is_transient = any(
                        status in exc_str 
                        for status in ["503", "429", "unavailable", "rate limit", "overloaded", "quota"]
                    )
                    
                    if is_transient and attempt < retries - 1:
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
                    else:
                        break
            
            if successful_model:
                break

        if not successful_model:
            raise last_error if last_error else Exception("All models failed.")

        ai_text = response.text if response and response.text else None

        return {
            "ai_analysis": ai_text,
            "model_used": successful_model,
            "error": None,
        }

    except Exception as exc:
        traceback.print_exc()
        return {
            "ai_analysis": None,
            "model_used": model,
            "error": f"Gemini API error: {str(exc)}",
        }


