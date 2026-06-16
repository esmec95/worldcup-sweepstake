#!/usr/bin/env python3
"""Fetch WC 2026 results from football-data.org and write results.json."""

import json
import os
import sys
from datetime import date
import urllib.request

API_KEY = os.environ["FOOTBALL_API_KEY"]
COMPETITION = "WC"
SEASON = "2026"

# football-data.org name → sweepstake name
NAME_MAP = {
    "Mexico": "Mexico",
    "South Africa": "South Africa",
    "Korea Republic": "South Korea",
    "Czechia": "Czechia",
    "Czech Republic": "Czechia",
    "Canada": "Canada",
    "Bosnia and Herzegovina": "Bosnia",
    "United States": "USA",
    "Paraguay": "Paraguay",
    "Qatar": "Qatar",
    "Switzerland": "Switzerland",
    "Brazil": "Brazil",
    "Morocco": "Morocco",
    "Scotland": "Scotland",
    "Haiti": "Haiti",
    "Australia": "Australia",
    "Türkiye": "Turkiye",
    "Turkey": "Turkiye",
    "Germany": "Germany",
    "Curaçao": "Curacao",
    "Netherlands": "Netherlands",
    "Japan": "Japan",
    "Côte d'Ivoire": "Ivory Coast",
    "Ecuador": "Ecuador",
    "Sweden": "Sweden",
    "Tunisia": "Tunisia",
    "Spain": "Spain",
    "Cabo Verde": "Cape Verde",
    "Cape Verde": "Cape Verde",
    "Saudi Arabia": "Saudi Arabia",
    "Uruguay": "Uruguay",
    "Belgium": "Belgium",
    "Egypt": "Egypt",
    "Iran": "Iran",
    "IR Iran": "Iran",
    "New Zealand": "New Zealand",
    "Ghana": "Ghana",
    "Panama": "Panama",
    "Iraq": "Iraq",
    "Uzbekistan": "Uzbekistan",
    "Austria": "Austria",
    "Croatia": "Croatia",
    "Argentina": "Argentina",
    "France": "France",
    "Portugal": "Portugal",
    "DR Congo": "DR Congo",
    "Congo DR": "DR Congo",
    "Democratic Republic of Congo": "DR Congo",
    "Colombia": "Colombia",
    "Senegal": "Senegal",
    "England": "England",
    "Jordan": "Jordan",
    "Norway": "Norway",
    "Algeria": "Algeria",
}

SWEEPSTAKE_TEAMS = {
    "Mexico", "South Africa", "South Korea", "Czechia", "Canada", "Bosnia",
    "USA", "Paraguay", "Qatar", "Switzerland", "Brazil", "Morocco", "Scotland",
    "Haiti", "Australia", "Turkiye", "Germany", "Curacao", "Netherlands", "Japan",
    "Ivory Coast", "Ecuador", "Sweden", "Tunisia", "Spain", "Cape Verde",
    "Saudi Arabia", "Uruguay", "Belgium", "Egypt", "Iran", "New Zealand",
    "Ghana", "Panama", "Iraq", "Uzbekistan", "Austria", "Croatia", "Argentina",
    "France", "Portugal", "DR Congo", "Colombia", "Senegal", "England",
    "Jordan", "Norway", "Algeria",
}


def fetch_matches():
    url = f"https://api.football-data.org/v4/competitions/{COMPETITION}/matches?season={SEASON}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": API_KEY})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["matches"]


def classify(match, side):
    """Return (pts, label, cls) for one team in one match."""
    status = match["status"]
    ft = match["score"]["fullTime"]
    for_g  = ft["home"] if side == "home" else ft["away"]
    opp_g  = ft["away"] if side == "home" else ft["home"]

    if status == "FINISHED":
        if for_g > opp_g:
            return 3, f"W {for_g}–{opp_g}", "badge-win"
        elif for_g == opp_g:
            return 1, f"D {for_g}–{opp_g}", "badge-draw"
        else:
            return 0, f"L {for_g}–{opp_g}", "badge-loss"

    if status in ("IN_PLAY", "PAUSED", "HALFTIME"):
        h = ft.get("home") or 0
        a = ft.get("away") or 0
        live_for  = h if side == "home" else a
        live_opp  = a if side == "home" else h
        return 0, f"Live {live_for}–{live_opp}", "badge-playing"

    today = date.today().isoformat()
    if match["utcDate"][:10] == today:
        return 0, "Today", "badge-playing"
    return 0, "TBD", "badge-none"


def main():
    try:
        matches = fetch_matches()
    except Exception as exc:
        print(f"ERROR fetching matches: {exc}", file=sys.stderr)
        sys.exit(1)

    records = {t: [] for t in SWEEPSTAKE_TEAMS}
    unmapped = set()

    for m in matches:
        home_raw = m["homeTeam"]["name"]
        away_raw = m["awayTeam"]["name"]
        home = NAME_MAP.get(home_raw) if home_raw else None
        away = NAME_MAP.get(away_raw) if away_raw else None
        if home_raw and home is None:
            unmapped.add(home_raw)
        elif home in records:
            records[home].append(classify(m, "home"))
        if away_raw and away is None:
            unmapped.add(away_raw)
        elif away in records:
            records[away].append(classify(m, "away"))

    if unmapped:
        print(f"WARNING — unmapped team names from API (add these to NAME_MAP):")
        for name in sorted(unmapped):
            print(f"  \"{name}\"")

    results = {}
    live_teams = []

    for team, games in records.items():
        if not games:
            results[team] = {"pts": 0, "label": "TBD", "cls": "badge-none"}
            continue

        total_pts = sum(g[0] for g in games)
        live      = [g for g in games if g[2] == "badge-playing"]
        finished  = [g for g in games if g[2] in ("badge-win", "badge-draw", "badge-loss")]

        if live:
            _, label, cls = live[-1]
            live_teams.append(team)
        elif finished:
            wins   = sum(1 for g in finished if g[2] == "badge-win")
            draws  = sum(1 for g in finished if g[2] == "badge-draw")
            losses = sum(1 for g in finished if g[2] == "badge-loss")
            if len(finished) == 1:
                _, label, cls = finished[0]
            else:
                label = f"{wins}W {draws}D {losses}L"
                cls = "badge-win" if wins > losses else "badge-draw" if wins == losses else "badge-loss"
        else:
            _, label, cls = games[-1]

        results[team] = {"pts": total_pts, "label": label, "cls": cls}

    today_str = date.today().strftime("%d %B %Y").lstrip("0")
    note = (
        f"Matches in progress: {', '.join(sorted(live_teams))} — leaderboard refreshes every 5 minutes."
        if live_teams else ""
    )

    payload = {"lastUpdated": today_str, "note": note, "teams": results}
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Done — {len(results)} teams, {len(live_teams)} live now")


if __name__ == "__main__":
    main()
