#!/usr/bin/env python3
"""
用 GitHub Personal Access Token 设置仓库 description / homepage / topics。

用法：
    python3 set_repo_meta.py <你的PAT>
或
    GITHUB_PAT=ghp_xxx python3 set_repo_meta.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

REPO = "Erichestein0702/football-daily-push"
API = f"https://api.github.com/repos/{REPO}"

DESCRIPTION = ("⚽ 五大联赛+欧冠每日赛程/赛果自动抓取 → 中文日报 → 微信推送 "
               "(Python + GitHub Actions)")
HOMEPAGE = "https://github.com/Erichestein0702/football-daily-push"
TOPICS = ["football", "soccer", "espn", "github-actions", "python",
          "automation", "pushplus", "daily-report", "premier-league", "scraper"]


def gh(method: str, url: str, token: str, payload=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "football-daily-push-setup")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def main() -> int:
    token = (sys.argv[1] if len(sys.argv) > 1 else "") or os.environ.get("GITHUB_PAT", "")
    if not token:
        print("❌ 请提供 PAT：python3 set_repo_meta.py <PAT>  或设置 GITHUB_PAT 环境变量")
        return 2

    st, d = gh("GET", API, token)
    if st != 200:
        print(f"❌ 令牌无效或权限不足 (HTTP {st}): {d.get('message', d)}")
        return 1
    print(f"✅ 令牌有效，当前身份可访问仓库（private={d.get('private')}）")

    st, d = gh("PATCH", API, token, {
        "description": DESCRIPTION,
        "homepage": HOMEPAGE,
        "has_discussions": True,
    })
    if st == 200:
        print(f"✅ description = {d.get('description')}")
        print(f"✅ homepage    = {d.get('homepage')}")
        print(f"✅ has_discussions = {d.get('has_discussions')}")
    else:
        print(f"❌ PATCH 仓库设置失败 (HTTP {st}): {d.get('message', d)}")

    st2, d2 = gh("PUT", f"{API}/topics", token, {"names": TOPICS})
    if st2 == 200:
        print(f"✅ topics = {', '.join(d2.get('names', []))}")
    else:
        print(f"❌ 设置 topics 失败 (HTTP {st2}): {d2.get('message', d2)}")

    st3, d3 = gh("GET", API, token)
    if st3 == 200:
        print("\n--- 最终复核 ---")
        print(f"  description : {d3.get('description')}")
        print(f"  homepage    : {d3.get('homepage')}")
        print(f"  topics      : {d3.get('topics')}")
        print(f"  visibility  : {d3.get('visibility')}")
        print(f"  URL         : {d3.get('html_url')}")
    return 0 if (st == 200 and st2 == 200) else 1


if __name__ == "__main__":
    sys.exit(main())
