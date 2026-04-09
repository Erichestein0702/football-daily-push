#!/usr/bin/env python3
"""
⚽ 五大联赛 + 欧冠 每日足球数据抓取
覆盖：英超、西甲、德甲、欧冠（无法甲意甲）
输出：JSON 格式数据，包含今日赛程 + 昨日结果
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============ 配置区 ============
TEAMS_HIGHLIGHT = {"Manchester United": "⭐", "Barcelona": "⭐", "曼联": "⭐", "巴萨": "⭐"}
LEAGUES = ["Premier League", "La Liga", "Bundesliga", "UEFA Champions League"]
LEAGUE_NAMES_CN = {
    "Premier League": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超",
    "La Liga": "🇪🇸 西甲",
    "Bundesliga": "🇩🇪 德甲",
    "UEFA Champions League": "🏆 欧冠",
}
# ============ 配置区 ============


class FootballFetcher:
    """足球数据抓取器"""

    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })

    def get_api_url(self, league_id: str, date: str) -> str:
        """构建 API URL"""
        return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard?dates={date}"

    def fetch_league_data(self, league_id: str, date: str) -> dict:
        """抓取单个联赛某日数据"""
        url = self.get_api_url(league_id, date)
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e), "events": []}

    def extract_match_info(self, event: dict, highlight_teams: set) -> Optional[dict]:
        """从事件中提取比赛信息"""
        try:
            comp = event.get("competition", "")
            # 联赛过滤
            league_short = comp.upper().replace("UEFA CHAMPIONS LEAGUE", "UCL")
            if "PREMIER LEAGUE" not in league_short and "LALIGA" not in league_short \
               and "BUNDESLIGA" not in league_short and "UCL" not in league_short:
                return None

            home = event.get("homeTeam", {})
            away = event.get("awayTeam", {})
            home_name = home.get("name", "")
            away_name = away.get("name", "")

            # 标记重点球队
            star = ""
            if home_name in highlight_teams or any(t in home_name for t in highlight_teams):
                star = "⭐"
            if away_name in highlight_teams or any(t in away_name for t in highlight_teams):
                star = "⭐"

            # 比分
            score = event.get("lastEvent", {})
            winner = score.get("winner", "")
            home_score = score.get("homeScore", {}).get("value", "-")
            away_score = score.get("awayScore", {}).get("value", "-")

            if winner == "home":
                score_display = f"**{home_score} - {away_score}**"
            elif winner == "away":
                score_display = f"**{home_score} - {away_score}**"
            else:
                score_display = f"{home_score} - {away_score}"

            # 开球时间（UTC 转北京时间 +8）
            start_time = event.get("date", "")
            if start_time:
                utc_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                cn_time = utc_time + timedelta(hours=8)
                time_display = cn_time.strftime("%H:%M")
            else:
                time_display = "时间待定"

            return {
                "league": comp,
                "home": home_name,
                "away": away_name,
                "star": star,
                "score": score_display,
                "time": time_display,
                "status": event.get("status", {}).get("type", {}).get("name", ""),
                "has_odds": bool(event.get("odds", [])),
            }
        except Exception:
            return None

    def build_report(self, league_data: dict, league_name: str, match_type: str) -> str:
        """构建单个联赛的 Markdown 报告"""
        lines = [f"\n### {league_name}\n"]
        events = league_data.get("events", [])

        if not events:
            lines.append("*暂无赛事*\n")
            return "".join(lines)

        for event in events:
            info = self.extract_match_info(event, TEAMS_HIGHLIGHT)
            if info is None:
                continue
            star = info["star"]
            time = info["time"]
            home = info["home"]
            away = info["away"]

            if match_type == "result":
                score = info["score"]
                lines.append(f"{star} {home} {score} {away}\n")
            else:
                lines.append(f"{star} {time} {home} vs {away}\n")

        return "".join(lines)


def main():
    now = datetime.now(timezone(timedelta(hours=8)))
    today = now.strftime("%Y%m%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")

    fetcher = FootballFetcher()

    # 联赛 ID 映射
    league_map = {
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超": ("eng.1", "Premier League"),
        "🇪🇸 西甲": ("esp.1", "La Liga"),
        "🇩🇪 德甲": ("ger.1", "Bundesliga"),
        "🏆 欧冠": ("uefa.champions", "UEFA Champions League"),
    }

    report = f"# ⚽ 足球日报 — {now.strftime('%Y年%m月%d日')}\n"
    report += f"生成时间：{now.strftime('%H:%M:%S')}\n"

    # 昨日结果
    report += "\n## 📊 昨日赛果\n"
    for cn_name, ( league_id, eng_name) in league_map.items():
        data = fetcher.fetch_league_data(league_id, yesterday)
        report += fetcher.build_report(data, eng_name, "result")

    # 今日赛程
    report += "\n## 📅 今日赛程\n"
    for cn_name, (league_id, eng_name) in league_map.items():
        data = fetcher.fetch_league_data(league_id, today)
        report += fetcher.build_report(data, eng_name, "schedule")

    # 写入文件
    output_path = "football_daily.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written to {output_path}")

    # 输出 JSON 结构供 GitHub Actions 使用
    output_json = "football_data.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"report": report, "date": today}, f, ensure_ascii=False, indent=2)

    print(f"JSON data written to {output_json}")


if __name__ == "__main__":
    main()
