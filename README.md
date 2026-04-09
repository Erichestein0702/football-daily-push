# ⚽ 足球日报自动推送

每天北京时间 08:00 自动抓取英超、西甲、德甲、欧冠比赛数据，推送到微信。

## 覆盖联赛

- 🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超（Premier League）
- 🇪🇸 西甲（La Liga）
- 🇩🇪 德甲（Bundesliga）
- 🏆 欧冠（UEFA Champions League）

## 推送内容

- 昨日比赛结果（比分）
- 今日赛程（开球时间）
- 重点关注球队标记（⭐ 曼联、⭐ 巴萨）
- 欧冠附带赔率信息

## 微信推送配置

需要配置 `PUSHPLUS_TOKEN` secret：

1. 打开 [pushplus.plus](https://www.pushplus.plus)，微信扫码登录
2. 复制你的 Token
3. 在 GitHub 仓库 Settings → Secrets → Actions → New repository secret
4. 名称填 `PUSHPLUS_TOKEN`，值填你的 Token

## 手动触发

仓库 Actions 页面 → "⚽ 每日足球推送" → Run workflow

## 本地运行

```bash
pip install requests
python fetch_football.py
```
