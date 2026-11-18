<div align="center">

# ⚽ Football Daily Push

**五大联赛 + 欧冠 · 每日赛程与赛果自动推送**

[![Daily Push](https://github.com/Erichestein0702/football-daily-push/actions/workflows/daily_push.yml/badge.svg)](https://github.com/Erichestein0702/football-daily-push/actions/workflows/daily_push.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Data Source](https://img.shields.io/badge/data-ESPN%20Scoreboard%20API-orange.svg)](https://site.api.espn.com/apis/site/v2/sports/soccer)

每天早晨自动抓取 **英超 / 西甲 / 德甲 / 意甲 / 法甲 / 欧冠** 的比赛数据，
整理成中文日报并推送到微信，同时将日报归档回仓库。

</div>

---

## 📸 效果预览

<div align="center">
  <img src="assets/preview.png" alt="足球日报推送效果预览" width="380">
</div>

> 实际推送内容示例（节选）：
>
> ```
> # ⚽ 足球日报 · 2025年11月01日
>
> > 生成时间：2025-11-01 08:00:03（北京时间） · 数据源：ESPN
>
> ## 📊 昨日赛果
>
> ### 🇪🇸 西甲
> - ⭐ Atlético Madrid **3 - 0** Sevilla  <sub>· 马竞</sub>
>
> ## 📅 今日赛程
>
> ### 🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超
> - ⭐ 11-01 23:00 Nottingham Forest **2 - 2** Manchester United  <sub>· 完场</sub>
> - 11-01 23:00 Crystal Palace **2 - 0** Brentford  <sub>· 完场</sub>
> ```

---

## 🎯 覆盖范围

| 联赛 | ESPN 联赛 ID | 标识 |
|:--|:--|:--|
| 英超 Premier League | `eng.1` | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 |
| 西甲 La Liga | `esp.1` | 🇪🇸 |
| 德甲 Bundesliga | `ger.1` | 🇩🇪 |
| 意甲 Serie A | `ita.1` | 🇮🇹 |
| 法甲 Ligue 1 | `fra.1` | 🇫🇷 |
| 欧冠 UEFA Champions League | `uefa.champions` | 🏆 |

**推送内容**

- 📊 **昨日赛果** —— 已完场比分，胜方比分加粗
- 📅 **今日赛程** —— 按北京时间标注开球时间，未开始/进行中/完场状态一目了然
- ⭐ **重点球队** —— 曼联、曼城、利物浦、阿森纳、切尔西、热刺、巴萨、皇马、马竞、拜仁、多特、国米、米兰、尤文自动标记
- 🔤 **中文队名** —— 重点球队附带中文简称（如「曼联」「巴萨」）

---

## ✨ 特性

- 🕐 **时区正确** —— ESPN 按 UTC 日期分桶，日报严格按**北京时间**归类。跨天赛事（如 UTC 20:00 → 北京次日 04:00）不会错位
- ⚡ **并发抓取** —— 6 个联赛 × 3 个日期桶并行请求，整体耗时数秒
- 🛡️ **容错重试** —— 内置指数退避重试，单个联赛失败不影响其余联赛
- 🔍 **错误可见** —— 抓取失败会在日报顶部以警示块列出，区分「今天没比赛」与「接口挂了」
- 🔐 **密钥安全** —— 微信推送 Token 仅存于 GitHub Secrets，从不写入仓库
- 📦 **历史归档** —— 每日日报自动提交回仓库，可回溯任意一天

---

## 🚀 快速开始

### 本地运行

```bash
git clone https://github.com/Erichestein0702/football-daily-push.git
cd football-daily-push

python -m pip install -r requirements.txt

# 抓取今天（北京时间）
python fetch_football.py

# 抓取指定日期
python fetch_football.py --date 2025-11-01
```

运行后会在当前目录生成两个文件：

| 文件 | 说明 |
|:--|:--|
| `football_daily.md` | Markdown 日报（微信推送与提交归档用） |
| `football_data.json` | 结构化数据，含 UTC/北京双时区时间、状态、比分、是否命中重点球队 |

### 微信推送（可选）

```bash
export PUSHPLUS_TOKEN=你的PushPlus令牌
python notify_pushplus.py
```

未设置该环境变量时脚本会直接跳过并返回 0，不会中断 CI。

---

## ⚙️ 配置微信推送

推送通道使用 [PushPlus](https://www.pushplus.plus)，配置步骤：

1. 打开 [pushplus.plus](https://www.pushplus.plus)，微信扫码登录
2. 复制个人中心的 **Token**
3. 进入仓库 **Settings → Secrets and variables → Actions → New repository secret**
4. Name 填 `PUSHPLUS_TOKEN`，Value 粘贴 Token
5. 保存后手动触发一次工作流验证

> 💡 私钥类信息只保存在 Actions Secrets 中，仓库代码与提交历史中均不含真实 Token。
>
> ⚠️ **未配置时的表现**：工作流会打印「未配置 PUSHPLUS_TOKEN，跳过微信推送」并正常结束，
> 日报仍会生成并归档到仓库 —— 不会导致整个任务失败。

---

## 🔄 工作流说明

工作流定义在 [`.github/workflows/daily_push.yml`](.github/workflows/daily_push.yml)。

| 触发方式 | 说明 |
|:--|:--|
| `schedule` | 每天 **08:00（北京时间 / UTC 00:00）** 自动执行 |
| `workflow_dispatch` | 仓库 Actions 页面手动触发，可选填 `date` 参数回溯指定日期 |

**执行流程**

```
Checkout (完整历史)
   └─> 安装依赖
          └─> 抓取数据  ──>  推送微信 (PushPlus)
                 └─> 提交日报回仓库
```

关键配置说明：

- `permissions: contents: write` —— 允许工作流写回日报文件
- `fetch-depth: 0` —— 保留完整历史，保证 `git pull --rebase` 正常
- `concurrency` —— 避免定时任务与手动触发并发写入冲突

> 💡 日报正文通过独立的 `notify_pushplus.py` 直接读取文件并构造 JSON 请求，
> 不再经由 `$GITHUB_OUTPUT` 传递 —— 多行内容写进 `GITHUB_OUTPUT` 会导致
> `Invalid format` 错误使整个工作流失败（这正是旧版本连续失败的原因）。

### 手动回溯历史日期

在 Actions 页面触发工作流时，可填入 `date` 参数抓取任意一天：

```yaml
workflow_dispatch:
  inputs:
    date:
      description: "抓取指定日期（YYYY-MM-DD，北京时间），留空则使用当天"
```

```bash
# 等价于本地执行
python fetch_football.py --date 2025-11-01
```

---

## 🧩 项目结构

```
football-daily-push/
├── .github/
│   └── workflows/
│       └── daily_push.yml     # 定时抓取与推送工作流
├── assets/
│   └── preview.png            # README 预览图
├── fetch_football.py          # 核心：数据抓取与日报生成
├── notify_pushplus.py         # 微信（PushPlus）推送
├── requirements.txt           # Python 依赖
├── LICENSE                    # MIT 许可证
├── README.md
└── .gitignore
```

### 核心模块

| 模块 | 职责 |
|:--|:--|
| `FootballFetcher.fetch_day()` | 请求 ESPN Scoreboard 单日桶 |
| `FootballFetcher.fetch_league_window()` | 跨 UTC 桶抓取并按北京时间归类 |
| `FootballFetcher.parse_event()` | 解析 `competitions[0].competitors` 结构，输出标准化 `Match` |
| `collect()` | 多线程并发抓取全部联赛 |
| `render_markdown()` | 渲染中文 Markdown 日报 |
| `build_json()` | 构建结构化 JSON 输出 |

---

## 🧭 实现要点

### 1. 为什么不能用 `event["homeTeam"]`

ESPN Scoreboard API 的真实结构是**嵌套的**：

```
event
└── competitions[0]
    ├── competitors[]      ←  主客队在这里
    │   ├── homeAway: "home" / "away"
    │   ├── score: "2"
    │   ├── winner: true
    │   └── team.displayName: "Manchester United"
    └── status.type.name: "STATUS_FULL_TIME"
```

顶层事件只有 `id / uid / date / name / shortName / season / competitions / status / venue / links`。
直接读 `event["homeTeam"]` 或 `event["lastEvent"]` 只会拿到 `None`，
导致**所有赛事被静默过滤，日报恒为空**。

### 2. 时区为什么要跨桶

ESPN 的 `dates=YYYYMMDD` 按 **UTC** 分桶，而欧洲赛事集中在 UTC 12:00–21:00，
换算成北京时间后常落在**次日**。

因此本项目对每个目标日期抓取 `D-1 / D / D+1` 三个 UTC 桶，
再用 `kickoff_utc.astimezone(BJT).date()` 重新归类，确保「今天」在北京时间口径下准确无误。

### 3. 重点球队匹配为什么不能简单 `in`

ESPN 队名带变音符与前后缀差异（如 `Atlético Madrid` vs `Atletico Madrid`、
`1. FC Union Berlin` vs `Union Berlin`）。
直接字符串包含判断会漏配或误配，故采用**小写 + 去变音符 + 去 FC/AC/SS 前后缀**的规范化匹配。

---

## ❓ 常见问题

**Q：日报显示「今日无赛事安排」，是脚本坏了吗？**

不是。足球联赛存在**国际比赛日休赛期**，且各联赛赛程不同，
休赛期间本就没有比赛。可在 [ESPN Scoreboard](https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard)
直接核对。日报顶部若出现 ⚠️ 警示块，才代表抓取异常。

**Q：微信没收到推送？**

1. 确认 `PUSHPLUS_TOKEN` secret 已配置
2. 手动触发工作流，在日志中查看 `Push to WeChat via PushPlus` 步骤输出
3. 确认 PushPlus 令牌未过期

**Q：工作流提交失败？**

已配置 `git pull --rebase origin main` 处理并发冲突；
若仍失败，通常是 `permissions` 缺少 `contents: write`（本仓库已内置）。

**Q：可以改成其他时间推送吗？**

修改 [`.github/workflows/daily_push.yml`](.github/workflows/daily_push.yml) 中的 `cron`。
注意 cron 使用 **UTC** 时间，北京时间 = UTC + 8。
例如北京时间 07:00 → `cron: "0 23 * * *"`。

**Q：怎么把仓库改成 Public？**

仓库 **Settings → 底部 Danger Zone → Change repository visibility → Make public**，
按提示输入仓库名确认即可。

> ⚠️ 自动化工具使用的 GitHub App 令牌仅有 `administration: read` 权限，
> 无法代为修改仓库可见性，这一步需要你本人操作。

**Q：想让仓库更容易被搜到吗？**

在 **Settings → Topics** 添加：

```
football, soccer, espn, github-actions, python, automation, pushplus, daily-report
```

---

## 📄 许可证

[MIT](LICENSE) © Erichestein0702

数据来源：[ESPN Scoreboard API](https://site.api.espn.com/apis/site/v2/sports/soccer)，仅供个人学习与非商业用途。

---

<div align="center">
  <sub>由 GitHub Actions 自动驱动 · 用 ⚽ 和一点点 Python 驱动</sub>
</div>
