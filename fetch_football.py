#!/usr/bin/env python3
"""
⚽ 五大联赛 + 欧冠 每日足球数据抓取

数据源：ESPN 公开 Scoreboard API
输出  ：Markdown 日报（football_daily.md）+ 结构化 JSON（football_data.json）

设计要点
--------
1. ESPN 的 ``dates=YYYYMMDD`` 按 **UTC 日期** 分桶，而中文用户关心的是 **北京时间**。
   欧洲赛事集中在 UTC 12:00–21:00，换算后常落在北京时间次日，
   因此这里同时拉取 D-1 / D / D+1 三个桶，再按北京时间重新归类。
2. 赛事结构位于 ``event["competitions"][0]["competitors"]``，通过 ``homeAway``
   区分主客队；比分取 ``competitor["score"]``，胜方取 ``competitor["winner"]``。
3. 抓取失败会被记录并汇总输出，而不是静默吞掉，避免"今天没球"和"接口挂了"混淆。
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================== 配置区 ==============================

BJT = timezone(timedelta(hours=8), name="CST")

#: ESPN scoreboard 的联赛 ID
API_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LEAGUES: list[dict[str, str]] = [
    {"id": "eng.1", "name": "英超", "en": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"id": "esp.1", "name": "西甲", "en": "La Liga", "flag": "🇪🇸"},
    {"id": "ger.1", "name": "德甲", "en": "Bundesliga", "flag": "🇩🇪"},
    {"id": "ita.1", "name": "意甲", "en": "Serie A", "flag": "🇮🇹"},
    {"id": "fra.1", "name": "法甲", "en": "Ligue 1", "flag": "🇫🇷"},
    {"id": "uefa.champions", "name": "欧冠", "en": "UEFA Champions League", "flag": "🏆"},
]

#: 重点关注的球队（ESPN displayName 全称，匹配时做规范化比较）
HIGHLIGHT_TEAMS: dict[str, str] = {
    "Manchester United": "曼联",
    "Manchester City": "曼城",
    "Liverpool": "利物浦",
    "Arsenal": "阿森纳",
    "Chelsea": "切尔西",
    "Tottenham Hotspur": "热刺",
    "Barcelona": "巴萨",
    "Real Madrid": "皇马",
    "Atletico Madrid": "马竞",
    "Atlético Madrid": "马竞",
    "Bayern Munich": "拜仁",
    "Borussia Dortmund": "多特",
    "Inter Milan": "国米",
    "Internazionale": "国米",
    "AC Milan": "米兰",
    "Juventus": "尤文",
}

#: 命中重点球队时的标记
STAR = "⭐"

#: 网络请求参数
TIMEOUT = 20
MAX_RETRY = 3
BACKOFF = 1.0
WORKERS = 6

# ==================================================================


@dataclass
class Match:
    """单场比赛的标准化记录"""

    league_id: str
    league_name: str
    home: str
    away: str
    kickoff_utc: datetime
    kickoff_bjt: datetime
    status: str = ""
    completed: bool = False
    home_score: str = "-"
    away_score: str = "-"
    winner: str = ""  # "home" / "away" / ""
    starred: list[str] = field(default_factory=list)

    @property
    def time_text(self) -> str:
        return self.kickoff_bjt.strftime("%m-%d %H:%M")

    @property
    def score_text(self) -> str:
        if not self.completed:
            return "vs"
        return f"{self.home_score} - {self.away_score}"

    @property
    def status_text(self) -> str:
        return {
            "STATUS_FULL_TIME": "完场",
            "STATUS_SCHEDULED": "未开始",
            "STATUS_IN_PROGRESS": "进行中",
            "STATUS_HALFTIME": "中场",
            "STATUS_POSTPONED": "延期",
            "STATUS_CANCELED": "取消",
        }.get(self.status, self.status.replace("STATUS_", ""))


def normalize(name: str) -> str:
    """队名规范化：小写 + 去重音 + 去除 FC/AC/SS 等前后缀噪声"""
    text = name.strip().lower()
    for ch in ("á", "à", "â", "ä", "é", "è", "ê", "ë", "í", "ì", "î", "ï",
               "ó", "ò", "ô", "ö", "ú", "ù", "û", "ü", "ñ", "ç"):
        text = text.replace(ch, {"á": "a", "à": "a", "â": "a", "ä": "a",
                                  "é": "e", "è": "e", "ê": "e", "ë": "e",
                                  "í": "i", "ì": "i", "î": "i", "ï": "i",
                                  "ó": "o", "ò": "o", "ô": "o", "ö": "o",
                                  "ú": "u", "ù": "u", "û": "u", "ü": "u",
                                  "ñ": "n", "ç": "c"}[ch])
    for token in (" fc ", " ac ", " ss ", " sc ", " afc ", " cf "):
        text = text.replace(token, " ")
    return " ".join(text.split())


#: 规范化后的队名 -> 中文简称
_HIGHLIGHT_INDEX: dict[str, str] = {}
for _en, _cn in HIGHLIGHT_TEAMS.items():
    _HIGHLIGHT_INDEX.setdefault(normalize(_en), _cn)


def highlight_of(name: str) -> str | None:
    """若球队命中重点名单，返回中文简称，否则返回 None"""
    key = normalize(name)
    if key in _HIGHLIGHT_INDEX:
        return _HIGHLIGHT_INDEX[key]
    # "Internazionale" 与 "Inter Milan" 互为别名
    alias = {
        "internazionale": "国米",
        "inter milan": "国米",
        "ac milan": "米兰",
        "atletico madrid": "马竞",
        "tottenham hotspur": "热刺",
        "tottenham": "热刺",
    }
    return alias.get(key)


class FootballFetcher:
    """ESPN scoreboard 数据抓取器"""

    def __init__(self) -> None:
        self.session = requests.Session()
        retry = Retry(
            total=MAX_RETRY,
            backoff_factor=BACKOFF,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=WORKERS, pool_maxsize=WORKERS)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })

    def fetch_day(self, league_id: str, day: date) -> list[dict[str, Any]]:
        """抓取某联赛某一天（ESPN 桶）的原始 events"""
        url = f"{API_BASE}/{league_id}/scoreboard?dates={day:%Y%m%d}"
        resp = self.session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("events", []) or []

    def fetch_league_window(self, league_id: str, days: Iterable[date]) -> list[Match]:
        """
        抓取目标北京时间日期附近的所有赛事。

        ESPN 按 UTC 日期分桶，而北京时间日期 D 的赛事其 UTC 时刻落在
        [D-1 16:00Z, D 15:59Z]，即分属 UTC 的 D-1 与 D 两个桶。
        因此对一组目标北京时间日期，需要额外向前后各扩一天抓取 UTC 桶，
        最后再按北京时间重新归类。
        """
        days = list(days)
        lo = min(days) - timedelta(days=1)
        hi = max(days) + timedelta(days=1)
        wanted = set(days)

        events: list[dict[str, Any]] = []
        bucket = lo
        while bucket <= hi:
            events.extend(self.fetch_day(league_id, bucket))
            bucket += timedelta(days=1)

        matches: list[Match] = []
        for event in events:
            match = self.parse_event(event, league_id)
            if match is None:
                continue
            if match.kickoff_bjt.date() in wanted:
                matches.append(match)

        matches.sort(key=lambda m: m.kickoff_bjt)
        return matches

    def parse_event(self, event: dict[str, Any], league_id: str) -> Match | None:
        """从 ESPN event 字典解析出标准化的 Match"""
        competitions = event.get("competitions") or []
        if not competitions:
            return None
        comp = competitions[0]

        competitors = comp.get("competitors") or []
        home_c = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away_c = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if home_c is None or away_c is None:
            return None

        home_name = (home_c.get("team") or {}).get("displayName", "主队")
        away_name = (away_c.get("team") or {}).get("displayName", "客队")

        raw_date = event.get("date") or comp.get("date")
        if not raw_date:
            return None
        try:
            kickoff_utc = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        except ValueError:
            return None
        if kickoff_utc.tzinfo is None:
            kickoff_utc = kickoff_utc.replace(tzinfo=timezone.utc)

        status_type = (event.get("status") or comp.get("status") or {}).get("type") or {}
        completed = bool(status_type.get("completed"))

        winner = ""
        if completed:
            if home_c.get("winner"):
                winner = "home"
            elif away_c.get("winner"):
                winner = "away"

        starred = [cn for cn in (highlight_of(home_name), highlight_of(away_name)) if cn]

        league = next((lg for lg in LEAGUES if lg["id"] == league_id), None)
        return Match(
            league_id=league_id,
            league_name=league["name"] if league else league_id,
            home=home_name,
            away=away_name,
            kickoff_utc=kickoff_utc,
            kickoff_bjt=kickoff_utc.astimezone(BJT),
            status=status_type.get("name", ""),
            completed=completed,
            home_score=str(home_c.get("score", "-")),
            away_score=str(away_c.get("score", "-")),
            winner=winner,
            starred=starred,
        )


def collect(fetcher: FootballFetcher, target: date) -> tuple[dict[str, list[Match]], list[str]]:
    """并发抓取所有联赛，返回 (结果, 错误列表)"""
    results: dict[str, list[Match]] = {}
    errors: list[str] = []
    # 同时抓取"昨日"与"今日"两个北京时间日期
    wanted = [target - timedelta(days=1), target]

    def worker(league: dict[str, str]) -> tuple[str, list[Match], str | None]:
        try:
            return league["id"], fetcher.fetch_league_window(league["id"], wanted), None
        except Exception as exc:  # noqa: BLE001 - 单个联赛失败不应影响整体
            return league["id"], [], f"{league['name']}：{exc.__class__.__name__} {exc}"

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for league_id, matches, error in pool.map(worker, LEAGUES):
            results[league_id] = matches
            if error:
                errors.append(error)

    return results, errors


def render_markdown(target: date, results: dict[str, list[Match]], errors: list[str],
                    generated_at: datetime) -> str:
    """渲染 Markdown 日报"""
    lines: list[str] = []
    lines.append(f"# ⚽ 足球日报 · {target:%Y年%m月%d日}")
    lines.append("")
    lines.append(f"> 生成时间：{generated_at:%Y-%m-%d %H:%M:%S}（北京时间） · 数据源：ESPN")
    lines.append("")

    if errors:
        lines.append("> [!WARNING]")
        lines.append("> 以下联赛本次抓取失败，数据可能不完整：")
        for err in errors:
            lines.append(f"> - {err}")
        lines.append("")

    # ---- 昨日赛果 ----
    yesterday = target - timedelta(days=1)
    lines.append("## 📊 昨日赛果")
    lines.append("")
    yesterday_any = False
    for league in LEAGUES:
        matches = [m for m in results.get(league["id"], [])
                   if m.kickoff_bjt.date() == yesterday and m.completed]
        if not matches:
            continue
        yesterday_any = True
        lines.append(f"### {league['flag']} {league['name']}")
        lines.append("")
        for m in matches:
            mark = f"{STAR} " if m.starred else ""
            score = f"**{m.home_score} - {m.away_score}**"
            lines.append(f"- {mark}{m.home} {score} {m.away}"
                         + (f"  <sub>· {m.starred[0]}</sub>" if m.starred else ""))
        lines.append("")

    if not yesterday_any:
        lines.append("_昨日无已完场赛事_")
        lines.append("")

    # ---- 今日赛程 ----
    lines.append("## 📅 今日赛程")
    lines.append("")
    today_any = False
    for league in LEAGUES:
        matches = [m for m in results.get(league["id"], []) if m.kickoff_bjt.date() == target]
        if not matches:
            continue
        today_any = True
        lines.append(f"### {league['flag']} {league['name']}")
        lines.append("")
        for m in matches:
            mark = f"{STAR} " if m.starred else ""
            if m.completed:
                lines.append(f"- {mark}{m.time_text} {m.home} **{m.home_score} - {m.away_score}** "
                             f"{m.away} <sub>· {m.status_text}</sub>")
            else:
                lines.append(f"- {mark}{m.time_text} {m.home} vs {m.away} "
                             f"<sub>· {m.status_text}</sub>")
        lines.append("")

    if not today_any:
        lines.append("_今日无赛事安排_")
        lines.append("")

    # ---- 重点关注 ----
    starred_matches: list[Match] = []
    for matches in results.values():
        starred_matches.extend(m for m in matches if m.starred and m.kickoff_bjt.date() == target)
    if starred_matches:
        lines.append("## ⭐ 重点球队")
        lines.append("")
        for m in starred_matches:
            lines.append(f"- {m.time_text} {m.home} vs {m.away} <sub>· {'/'.join(m.starred)}</sub>")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("<sub>由 [football-daily-push](https://github.com/Erichestein0702/football-daily-push) "
                 "自动生成 · 数据来源 ESPN Scoreboard API</sub>")

    return "\n".join(lines).rstrip() + "\n"


def build_json(target: date, results: dict[str, list[Match]], errors: list[str],
               generated_at: datetime) -> dict[str, Any]:
    """构建结构化 JSON 输出"""
    payload: dict[str, Any] = {
        "date": f"{target:%Y-%m-%d}",
        "generated_at": generated_at.isoformat(),
        "timezone": "Asia/Shanghai (UTC+8)",
        "source": "ESPN Scoreboard API",
        "errors": errors,
        "leagues": [],
    }
    for league in LEAGUES:
        matches = [m for m in results.get(league["id"], [])
                   if m.kickoff_bjt.date() in (target - timedelta(days=1), target)]
        payload["leagues"].append({
            "id": league["id"],
            "name": league["name"],
            "name_en": league["en"],
            "flag": league["flag"],
            "matches": [
                {
                    "home": m.home,
                    "away": m.away,
                    "kickoff_utc": m.kickoff_utc.isoformat(),
                    "kickoff_bjt": m.kickoff_bjt.isoformat(),
                    "status": m.status,
                    "status_text": m.status_text,
                    "completed": m.completed,
                    "home_score": m.home_score,
                    "away_score": m.away_score,
                    "winner": m.winner,
                    "starred": m.starred,
                }
                for m in matches
            ],
        })
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取五大联赛与欧冠的每日赛程/赛果")
    parser.add_argument("--date", help="目标日期 YYYY-MM-DD（北京时间），默认今天")
    parser.add_argument("--md", default="football_daily.md", help="Markdown 输出路径")
    parser.add_argument("--json", default="football_data.json", help="JSON 输出路径")
    args = parser.parse_args()

    now = datetime.now(BJT)
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = now.date()

    fetcher = FootballFetcher()
    results, errors = collect(fetcher, target)

    total = sum(len(v) for v in results.values())
    completed = sum(1 for v in results.values() for m in v if m.completed)

    report = render_markdown(target, results, errors, now)
    payload = build_json(target, results, errors, now)

    with open(args.md, "w", encoding="utf-8") as fp:
        fp.write(report)
    with open(args.json, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    print(f"[fetch] 目标日期(北京) {target} | 赛事 {total} 场（已完场 {completed}）")
    print(f"[fetch] Markdown -> {args.md}")
    print(f"[fetch] JSON     -> {args.json}")
    if errors:
        for err in errors:
            print(f"[fetch] [ERROR] {err}", file=sys.stderr)

    # 全部联赛都失败时以非零码退出，让 CI 能感知到
    if total == 0 and errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
