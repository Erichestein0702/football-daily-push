#!/usr/bin/env python3
"""
⚽ 将当日足球日报推送到微信（PushPlus 通道）

用法：
    PUSHPLUS_TOKEN=xxxxxx python notify_pushplus.py

未配置 ``PUSHPLUS_TOKEN`` 时直接跳过并返回 0，方便在 CI 中无条件调用。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"
#: PushPlus 单条消息内容长度上限
MAX_CONTENT_CHARS = 19000
TIMEOUT = 30


def load_report(md_path: Path, json_path: Path) -> tuple[str, str]:
    """读取日报正文与日期"""
    content = md_path.read_text(encoding="utf-8")
    date_text = ""
    if json_path.exists():
        try:
            date_text = json.loads(json_path.read_text(encoding="utf-8")).get("date", "")
        except (json.JSONDecodeError, OSError):
            date_text = ""
    return content, date_text


def main() -> int:
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        print("[pushplus] 未配置 PUSHPLUS_TOKEN，跳过推送")
        return 0

    md_path = Path("football_daily.md")
    json_path = Path("football_data.json")
    if not md_path.exists():
        print(f"[pushplus] 未找到 {md_path}，跳过推送", file=sys.stderr)
        return 1

    content, date_text = load_report(md_path, json_path)

    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n> 内容过长，已截断"

    payload = {
        "token": token,
        "title": f"⚽ 足球日报 {date_text}".strip(),
        "content": content,
        "template": "markdown",
    }

    try:
        resp = requests.post(PUSHPLUS_ENDPOINT, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[pushplus] 推送失败：{exc}", file=sys.stderr)
        return 1

    try:
        result = resp.json()
    except ValueError:
        print(f"[pushplus] 响应非 JSON：{resp.text[:200]}")
        return 1

    code = result.get("code")
    msg = result.get("msg", "")
    if code == 200:
        print(f"[pushplus] 推送成功：{msg}")
        return 0

    print(f"[pushplus] 推送失败（code={code}）：{msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
