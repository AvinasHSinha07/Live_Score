import argparse
import math
import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def print_header(title: str) -> None:
	print(f"\n{'+' + '=' * 112 + '+'}")
	print(f"| {title.center(110)} |")
	print(f"{'+' + '=' * 112 + '+'}")


def print_section(title: str) -> None:
	print(f"\n>> {title.upper()} " + "-" * max(0, 104 - len(title)))


def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
	if total <= 0:
		return 0.0
	p_hat = successes / total
	denominator = 1 + (z ** 2 / total)
	center = p_hat + (z ** 2 / (2 * total))
	margin = z * math.sqrt((p_hat * (1 - p_hat) / total) + (z ** 2 / (4 * total ** 2)))
	return max(0.0, (center - margin) / denominator)


def round_half(x: float) -> float:
	return round(x * 2) / 2


def classify_pick(weighted_rate: float, confidence: float) -> str:
	if weighted_rate >= 0.68 and confidence >= 72:
		return "STRONG BET"
	if weighted_rate >= 0.58 and confidence >= 62:
		return "LEAN"
	if weighted_rate <= 0.38 and confidence >= 58:
		return "FADE"
	return "PASS"


def suggested_units(label: str, confidence: float, weighted_rate: float, bankroll: float) -> str:
	if label not in {"STRONG BET", "LEAN"}:
		return "0.00u"

	confidence_edge = max(0.0, (confidence - 58.0) / 32.0)
	trend_edge = max(0.0, (weighted_rate - 0.55) / 0.45)
	units = min(2.0, 0.50 + confidence_edge * 1.0 + trend_edge * 0.5)

	if label == "LEAN":
		units = min(units, 1.40)

	stake_cash = bankroll * (units / 100.0)
	return f"{units:.2f}u (~{stake_cash:.2f})"


def poisson_prob(k: int, lam: float) -> float:
	if lam <= 0:
		return 1.0 if k == 0 else 0.0
	return (lam ** k) * math.exp(-lam) / math.factorial(k)


def one_x_two_probabilities(exp_team: float, exp_opp: float, max_goals: int = 7) -> Dict[str, float]:
	p_win = 0.0
	p_draw = 0.0
	p_loss = 0.0

	for i in range(max_goals + 1):
		pi = poisson_prob(i, exp_team)
		for j in range(max_goals + 1):
			pj = poisson_prob(j, exp_opp)
			p = pi * pj
			if i > j:
				p_win += p
			elif i == j:
				p_draw += p
			else:
				p_loss += p

	total = p_win + p_draw + p_loss
	if total <= 0:
		return {"win": 0.0, "draw": 0.0, "loss": 0.0}

	return {
		"win": p_win / total,
		"draw": p_draw / total,
		"loss": p_loss / total,
	}


def ensure_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
	for col in cols:
		if col in df.columns:
			df[col] = pd.to_numeric(df[col], errors="coerce")
	return df


def load_recent_matches(csv_path: str, order: str, recent: Optional[int]) -> pd.DataFrame:
	if not os.path.exists(csv_path):
		raise FileNotFoundError(f"Could not find file: {csv_path}")

	df = pd.read_csv(csv_path)
	if df.empty:
		raise ValueError("CSV is empty.")

	numeric_cols = [
		"team_score",
		"opponent_score",
		"shots_on_target_team",
		"shots_on_target_opponent",
		"shots_off_target_team",
		"shots_off_target_opponent",
		"shots_blocked_team",
		"shots_blocked_opponent",
		"corners_team",
		"corners_opponent",
		"offsides_team",
		"offsides_opponent",
		"fouls_team",
		"fouls_opponent",
		"throw_ins_team",
		"throw_ins_opponent",
		"yellow_cards_team",
		"yellow_cards_opponent",
		"red_cards_team",
		"red_cards_opponent",
		"crosses_team",
		"crosses_opponent",
		"goalkeeper_saves_team",
		"goalkeeper_saves_opponent",
		"goal_kicks_team",
		"goal_kicks_opponent",
	]
	df = ensure_numeric(df, numeric_cols)
	df = df.dropna(subset=["team_score", "opponent_score"]).copy()

	if df.empty:
		raise ValueError("No valid rows with team_score and opponent_score.")

	if recent is not None and recent > 0:
		if order == "newest-first":
			df = df.head(recent).copy()
		else:
			df = df.tail(recent).copy()

	n = len(df)
	if n == 1:
		df["__weight"] = 1.0
	else:
		w = np.linspace(1.0, 1.8, n)
		if order == "newest-first":
			w = w[::-1]
		df["__weight"] = w

	return df


def weighted_mean(series: pd.Series, weights: pd.Series) -> float:
	mask = series.notna()
	if mask.sum() == 0:
		return float("nan")
	return float(np.average(series[mask], weights=weights[mask]))


def build_event_profiles(df: pd.DataFrame) -> List[Dict]:
	event_pairs = [
		("Goals", "team_score", "opponent_score"),
		("Shots On Target", "shots_on_target_team", "shots_on_target_opponent"),
		("Shots Off Target", "shots_off_target_team", "shots_off_target_opponent"),
		("Blocked Shots", "shots_blocked_team", "shots_blocked_opponent"),
		("Corners", "corners_team", "corners_opponent"),
		("Offsides", "offsides_team", "offsides_opponent"),
		("Fouls", "fouls_team", "fouls_opponent"),
		("Throw-Ins", "throw_ins_team", "throw_ins_opponent"),
		("Yellow Cards", "yellow_cards_team", "yellow_cards_opponent"),
		("Red Cards", "red_cards_team", "red_cards_opponent"),
		("Crosses", "crosses_team", "crosses_opponent"),
		("Goalkeeper Saves", "goalkeeper_saves_team", "goalkeeper_saves_opponent"),
		("Goal Kicks", "goal_kicks_team", "goal_kicks_opponent"),
	]

	out: List[Dict] = []
	for event_name, team_col, opp_col in event_pairs:
		if team_col not in df.columns or opp_col not in df.columns:
			continue

		valid = df[team_col].notna() & df[opp_col].notna()
		event_df = df[valid]
		if event_df.empty:
			continue

		sample = len(event_df)
		team_avg = weighted_mean(event_df[team_col], event_df["__weight"])
		opp_avg = weighted_mean(event_df[opp_col], event_df["__weight"])
		total_avg = team_avg + opp_avg

		dominance_raw = float((event_df[team_col] > event_df[opp_col]).mean())
		dominance_weighted = float(
			np.average((event_df[team_col] > event_df[opp_col]).astype(int), weights=event_df["__weight"])
		)

		edge = team_avg - opp_avg
		trend = "Balanced"
		if edge >= 0.55:
			trend = "Team Edge"
		elif edge <= -0.55:
			trend = "Opponent Edge"

		out.append(
			{
				"event": event_name,
				"sample": sample,
				"team_avg": team_avg,
				"opp_avg": opp_avg,
				"total_avg": total_avg,
				"edge": edge,
				"dominance_raw": dominance_raw,
				"dominance_weighted": dominance_weighted,
				"trend": trend,
			}
		)

	return out


def build_markets(df: pd.DataFrame) -> List[Dict]:
	market_defs: List[Dict] = [
		{
			"category": "Result",
			"name": "Team Win",
			"condition": lambda d: d["team_score"] > d["opponent_score"],
		},
		{
			"category": "Result",
			"name": "Team or Draw (1X)",
			"condition": lambda d: d["team_score"] >= d["opponent_score"],
		},
		{
			"category": "Result",
			"name": "Opponent or Draw (X2)",
			"condition": lambda d: d["team_score"] <= d["opponent_score"],
		},
		{
			"category": "Goals",
			"name": "Over 1.5 Match Goals",
			"condition": lambda d: (d["team_score"] + d["opponent_score"]) >= 2,
		},
		{
			"category": "Goals",
			"name": "Over 2.5 Match Goals",
			"condition": lambda d: (d["team_score"] + d["opponent_score"]) >= 3,
		},
		{
			"category": "Goals",
			"name": "Under 3.5 Match Goals",
			"condition": lambda d: (d["team_score"] + d["opponent_score"]) <= 3,
		},
		{
			"category": "Goals",
			"name": "Team Over 0.5 Goals",
			"condition": lambda d: d["team_score"] >= 1,
		},
		{
			"category": "Goals",
			"name": "Team Over 1.5 Goals",
			"condition": lambda d: d["team_score"] >= 2,
		},
		{
			"category": "Goals",
			"name": "Opponent Under 1.5 Goals",
			"condition": lambda d: d["opponent_score"] <= 1,
		},
		{
			"category": "BTTS",
			"name": "BTTS - Yes",
			"condition": lambda d: (d["team_score"] > 0) & (d["opponent_score"] > 0),
		},
		{
			"category": "BTTS",
			"name": "BTTS - No",
			"condition": lambda d: (d["team_score"] == 0) | (d["opponent_score"] == 0),
		},
	]

	if {"corners_team", "corners_opponent"}.issubset(df.columns):
		market_defs.extend(
			[
				{
					"category": "Corners",
					"name": "Over 8.5 Match Corners",
					"condition": lambda d: (d["corners_team"] + d["corners_opponent"]) >= 9,
					"valid": lambda d: d["corners_team"].notna() & d["corners_opponent"].notna(),
				},
				{
					"category": "Corners",
					"name": "Team Over 4.5 Corners",
					"condition": lambda d: d["corners_team"] >= 5,
					"valid": lambda d: d["corners_team"].notna(),
				},
				{
					"category": "Corners",
					"name": "Opponent Over 3.5 Corners",
					"condition": lambda d: d["corners_opponent"] >= 4,
					"valid": lambda d: d["corners_opponent"].notna(),
				},
			]
		)

	if {"yellow_cards_team", "yellow_cards_opponent"}.issubset(df.columns):
		market_defs.extend(
			[
				{
					"category": "Cards",
					"name": "Over 2.5 Match Yellow Cards",
					"condition": lambda d: (d["yellow_cards_team"] + d["yellow_cards_opponent"]) >= 3,
					"valid": lambda d: d["yellow_cards_team"].notna() & d["yellow_cards_opponent"].notna(),
				},
				{
					"category": "Cards",
					"name": "Team Over 1.5 Yellow Cards",
					"condition": lambda d: d["yellow_cards_team"] >= 2,
					"valid": lambda d: d["yellow_cards_team"].notna(),
				},
				{
					"category": "Cards",
					"name": "Opponent Over 1.5 Yellow Cards",
					"condition": lambda d: d["yellow_cards_opponent"] >= 2,
					"valid": lambda d: d["yellow_cards_opponent"].notna(),
				},
			]
		)

	if {"shots_on_target_team", "shots_on_target_opponent"}.issubset(df.columns):
		market_defs.extend(
			[
				{
					"category": "Shots",
					"name": "Team Over 3.5 Shots On Target",
					"condition": lambda d: d["shots_on_target_team"] >= 4,
					"valid": lambda d: d["shots_on_target_team"].notna(),
				},
				{
					"category": "Shots",
					"name": "Over 7.5 Match Shots On Target",
					"condition": lambda d: (d["shots_on_target_team"] + d["shots_on_target_opponent"]) >= 8,
					"valid": lambda d: d["shots_on_target_team"].notna() & d["shots_on_target_opponent"].notna(),
				},
			]
		)

	return market_defs


def evaluate_market(df: pd.DataFrame, market: Dict, bankroll: float) -> Dict:
	valid_fn = market.get("valid")
	valid_mask = valid_fn(df) if valid_fn else pd.Series(True, index=df.index)
	sub_df = df[valid_mask].copy()

	if sub_df.empty:
		return {
			"category": market["category"],
			"name": market["name"],
			"sample": 0,
			"raw_rate": 0.0,
			"weighted_rate": 0.0,
			"confidence": 0.0,
			"label": "PASS",
			"units": "0.00u",
			"note": "No data",
		}

	outcome = market["condition"](sub_df).astype(int)
	sample = len(sub_df)
	successes = int(outcome.sum())

	raw_rate = float(outcome.mean())
	weighted_rate = float(np.average(outcome, weights=sub_df["__weight"]))
	lower_bound = wilson_lower_bound(successes, sample)

	stability = 1.0 - min(1.0, abs(weighted_rate - raw_rate))
	sample_factor = min(1.0, 0.72 + sample / 35.0)
	confidence = (0.55 * weighted_rate + 0.30 * lower_bound + 0.15 * stability) * 100.0 * sample_factor
	confidence = max(0.0, min(99.0, confidence))

	label = classify_pick(weighted_rate, confidence)
	units = suggested_units(label, confidence, weighted_rate, bankroll)

	note = ""
	if sample < 6:
		note = "Small sample"
	elif abs(weighted_rate - raw_rate) > 0.14:
		note = "Volatile trend"

	return {
		"category": market["category"],
		"name": market["name"],
		"sample": sample,
		"raw_rate": raw_rate,
		"weighted_rate": weighted_rate,
		"confidence": confidence,
		"label": label,
		"units": units,
		"note": note,
	}


def infer_expected_goals(team_df: pd.DataFrame, opp_df: Optional[pd.DataFrame]) -> Dict[str, float]:
	team_attack = weighted_mean(team_df["team_score"], team_df["__weight"])
	team_defense = weighted_mean(team_df["opponent_score"], team_df["__weight"])

	if opp_df is None:
		exp_team = team_attack
		exp_opp = team_defense
	else:
		opp_attack = weighted_mean(opp_df["team_score"], opp_df["__weight"])
		opp_defense = weighted_mean(opp_df["opponent_score"], opp_df["__weight"])
		exp_team = 0.5 * (team_attack + opp_defense)
		exp_opp = 0.5 * (opp_attack + team_defense)

	return {
		"exp_team": max(0.1, exp_team),
		"exp_opp": max(0.1, exp_opp),
	}


def print_event_profile_table(profiles: List[Dict]) -> None:
	print_section("TEAM VS OPPONENT EVENT PROFILE (RECENT MATCHES)")
	print(
		f"{'Event':<18} {'Smp':>3} {'Team Avg':>9} {'Opp Avg':>9} {'Total':>9} "
		f"{'Edge':>8} {'Team>Opp':>10} {'W-Team>Opp':>12} Trend"
	)
	print("-" * 126)
	for p in profiles:
		print(
			f"{p['event']:<18} {p['sample']:>3d} {p['team_avg']:>8.2f} {p['opp_avg']:>8.2f} {p['total_avg']:>8.2f} "
			f"{p['edge']:>7.2f} {p['dominance_raw'] * 100:>9.1f}% {p['dominance_weighted'] * 100:>11.1f}% {p['trend']}"
		)


def print_market_table(results: List[Dict]) -> None:
	print_section("EVENT MARKET EVALUATION")
	print(
		f"{'Market':<38} {'Cat':<10} {'Smp':>3} {'Raw%':>7} {'Wgt%':>7} {'Conf':>6} "
		f"{'Call':<11} {'Stake':<14} Note"
	)
	print("-" * 138)
	for row in results:
		print(
			f"{row['name']:<38} {row['category']:<10} {row['sample']:>3d} "
			f"{row['raw_rate'] * 100:>6.1f}% {row['weighted_rate'] * 100:>6.1f}% {row['confidence']:>5.1f} "
			f"{row['label']:<11} {row['units']:<14} {row['note']}"
		)


def print_recommendation_plan(results: List[Dict], one_x_two: Dict[str, float]) -> None:
	print_section("ACTIONABLE MATCH PLAN")

	strong = [r for r in results if r["label"] == "STRONG BET"]
	lean = [r for r in results if r["label"] == "LEAN"]
	fade = [r for r in results if r["label"] == "FADE"]

	strong = sorted(strong, key=lambda x: (x["confidence"], x["weighted_rate"]), reverse=True)
	lean = sorted(lean, key=lambda x: (x["confidence"], x["weighted_rate"]), reverse=True)
	fade = sorted(fade, key=lambda x: (x["confidence"], -x["weighted_rate"]), reverse=True)

	print(
		f"Model 1X2: Win {one_x_two['win'] * 100:.1f}% | Draw {one_x_two['draw'] * 100:.1f}% | "
		f"Lose {one_x_two['loss'] * 100:.1f}%"
	)

	if strong:
		print("\nPrimary Bets:")
		for i, pick in enumerate(strong[:6], start=1):
			print(
				f" {i}. {pick['name']} | Conf {pick['confidence']:.1f} | "
				f"Weighted Hit {pick['weighted_rate'] * 100:.1f}% | Stake {pick['units']}"
			)
	else:
		print("\nPrimary Bets: no high-confidence edge. Skip main singles.")

	if lean:
		print("\nLean Bets (small stake only):")
		for i, pick in enumerate(lean[:5], start=1):
			print(
				f" {i}. {pick['name']} | Conf {pick['confidence']:.1f} | "
				f"Weighted Hit {pick['weighted_rate'] * 100:.1f}% | Stake {pick['units']}"
			)

	if fade:
		print("\nAvoid or Oppose:")
		for i, pick in enumerate(fade[:4], start=1):
			print(
				f" {i}. {pick['name']} | Weak profile ({pick['weighted_rate'] * 100:.1f}%) "
				f"with confidence {pick['confidence']:.1f}"
			)


def analyze(csv_path: str, bankroll: float, order: str, recent: Optional[int], opponent_csv: Optional[str]) -> None:
	team_df = load_recent_matches(csv_path, order=order, recent=recent)
	opponent_df = None
	if opponent_csv:
		opponent_df = load_recent_matches(opponent_csv, order=order, recent=recent)

	team_name = team_df["target_team"].iloc[0] if "target_team" in team_df.columns else "Target Team"
	opp_name = "Mixed Opponents"
	if opponent_df is not None:
		opp_name = opponent_df["target_team"].iloc[0] if "target_team" in opponent_df.columns else "Opponent"

	print_header(f"PRO MATCHUP EVENT ANALYZER: {team_name.upper()} VS {opp_name.upper()}")
	print(
		f"Matches Used: {len(team_df)} | Recency Order: {order} | Bankroll: {bankroll:.2f} | "
		f"Opponent CSV: {'YES' if opponent_df is not None else 'NO'}"
	)

	profiles = build_event_profiles(team_df)
	print_event_profile_table(profiles)

	markets = build_markets(team_df)
	results = [evaluate_market(team_df, m, bankroll) for m in markets]
	results = sorted(results, key=lambda x: (x["confidence"], x["weighted_rate"]), reverse=True)
	print_market_table(results)

	xg = infer_expected_goals(team_df, opponent_df)
	probs = one_x_two_probabilities(xg["exp_team"], xg["exp_opp"])

	print_section("EXPECTED GOALS MODEL")
	print(
		f"Expected Goals -> Team: {xg['exp_team']:.2f} | Opponent: {xg['exp_opp']:.2f} | "
		f"Expected Total: {xg['exp_team'] + xg['exp_opp']:.2f}"
	)

	print_recommendation_plan(results, probs)

	print_section("RISK MANAGEMENT")
	print("- Never treat any pick as guaranteed; this is probability guidance.")
	print("- Keep max single stake <= 2.00u and avoid chasing losses.")
	print("- If <2 strong bets exist, avoid parlays and focus on singles only.")


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Analyze all team and opponent recent-match events and generate useful betting predictions"
	)
	parser.add_argument("csv_file", help="Path to the target team CSV")
	parser.add_argument("--opponent-csv", default=None, help="Optional second CSV for opponent recent matches")
	parser.add_argument("--bankroll", type=float, default=100.0, help="Bankroll for stake guidance")
	parser.add_argument(
		"--order",
		choices=["newest-first", "oldest-first"],
		default="newest-first",
		help="Row order in CSV",
	)
	parser.add_argument(
		"--recent",
		type=int,
		default=None,
		help="Use only N recent matches from the given order",
	)

	args = parser.parse_args()

	try:
		analyze(
			csv_path=args.csv_file,
			bankroll=args.bankroll,
			order=args.order,
			recent=args.recent,
			opponent_csv=args.opponent_csv,
		)
	except Exception as exc:
		print(f"Error: {exc}")
