import requests

# 台灣 5/1 的比賽 = 美國東部 4/30
GAME_DATE = "20260430"
ESPN_URL = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={GAME_DATE}&seasontype=3"

TEAM_MAP = {
    "New York Knicks":           "尼克",
    "Atlanta Hawks":             "老鷹",
    "Boston Celtics":            "塞爾提克",
    "Philadelphia 76ers":        "76人",
    "Denver Nuggets":            "金塊",
    "Minnesota Timberwolves":    "灰狼",
}

MATCHES = {
    0: ("尼克",    "老鷹"),
    1: ("塞爾提克", "76人"),
    2: ("金塊",    "灰狼"),
}

FIRESTORE_URL = (
    "https://firestore.googleapis.com/v1/projects/"
    "gen-lang-client-0737444461/databases/(default)/"
    "documents/game_results/nba_0501"
)

def parse_event(event):
    if event["status"]["type"]["name"] != "STATUS_FINAL":
        return None, None, None
    comps = event["competitions"][0]["competitors"]
    away = next((c for c in comps if c["homeAway"] == "away"), comps[0])
    home = next((c for c in comps if c["homeAway"] == "home"), comps[1])
    winner_name = None
    for c in comps:
        if c.get("winner"):
            winner_name = TEAM_MAP.get(c["team"]["displayName"])
    return winner_name, away.get("score", ""), home.get("score", "")

ACTIVE_STATUSES = {"STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_FINAL", "STATUS_END_PERIOD"}
ALL_TEAMS = {t for a, b in MATCHES.values() for t in (a, b)}

def main():
    data = requests.get(ESPN_URL, timeout=10).json()

    relevant = [
        e for e in data.get("events", [])
        if {TEAM_MAP.get(c["team"]["displayName"]) for c in e["competitions"][0]["competitors"]} & ALL_TEAMS
    ]
    active = [e for e in relevant if e["status"]["type"]["name"] in ACTIVE_STATUSES]
    if not active:
        print("⏭ 比賽尚未開始，跳過更新")
        return

    results  = {i: None for i in range(3)}
    scores_a = {i: None for i in range(3)}
    scores_b = {i: None for i in range(3)}

    for event in data.get("events", []):
        comps = event["competitions"][0]["competitors"]
        away = next((c for c in comps if c["homeAway"] == "away"), comps[0])
        home = next((c for c in comps if c["homeAway"] == "home"), comps[1])
        away_zh = TEAM_MAP.get(away["team"]["displayName"])
        home_zh = TEAM_MAP.get(home["team"]["displayName"])
        team_names = {away_zh, home_zh}

        for mid, (a, b) in MATCHES.items():
            if team_names == {a, b}:
                winner, away_score, home_score = parse_event(event)
                if winner:
                    results[mid] = winner
                    if away_zh == a:
                        scores_a[mid], scores_b[mid] = away_score, home_score
                    else:
                        scores_a[mid], scores_b[mid] = home_score, away_score
                break

    print("📊 賽果:", results)

    fields = {}
    for i in range(3):
        fields[f"r{i}"] = {"stringValue": results[i]}  if results[i]  else {"nullValue": None}
        fields[f"a{i}"] = {"stringValue": scores_a[i]} if scores_a[i] else {"nullValue": None}
        fields[f"b{i}"] = {"stringValue": scores_b[i]} if scores_b[i] else {"nullValue": None}
        def margin_cat(sa, sb):
            if not sa or not sb: return None
            diff = abs(int(sa) - int(sb))
            if diff <= 10: return 0
            elif diff <= 20: return 1
            else: return 2
        mc = margin_cat(scores_a[i], scores_b[i])
        fields[f"m{i}"] = {"integerValue": str(mc)} if mc is not None else {"nullValue": None}

    field_names = [f"r{i}" for i in range(3)] + [f"a{i}" for i in range(3)] + [f"b{i}" for i in range(3)] + [f"m{i}" for i in range(3)]
    mask = "&".join(f"updateMask.fieldPaths={f}" for f in field_names)
    r = requests.patch(f"{FIRESTORE_URL}?{mask}", json={"fields": fields}, timeout=10)
    print("✅ 成功" if r.status_code == 200 else f"❌ {r.status_code}: {r.text}")

if __name__ == "__main__":
    main()
