# E8 复测记录 2026-09-21（搜索入口部分；元数据未读）

对应：[2026-09-17 基线](2026-09-17-probe.md)、[模板](template.md)、[决策 0001](../../docs/decisions/0001-project-name.md)。
性质：部分复测。9 条站内搜索查询重跑成功；仓库元数据（简介/topics/许可证）未读；网页端与普通搜索引擎未检查。

将改路径（AGENTS.md 第 18 条）：本文件为新建；另改 `docs/backlog.md`（W7 行指向本文件）。
不改 `docs/plan/v0.3.md`、仓库名、`LICENSE`、扩展代码、仓库设置。

## 条件

- 日期：2026-09-21（UTC）。操作者：实施者（技术核对）。
- 入口：GitHub REST Search API `GET /search/repositories`，未认证。字段范围等于 GitHub 默认仓库搜索（名称、简介、topics），排序为相关度。
- 检查窗口：每条查询前 20 名；本仓库位置记 20 名内下标，未进记 `null`（在本次窗口内未找到）。
- 当时元数据：未知。`GET /repos` 需核心配额，本轮实测核心 `remaining 0/60`（共享出口耗尽），按工程检查第 1 节“遇限流即停止”，未发起元数据读取。简介/topics/许可证是否变化均记未知，不沿用 9-17 基线当作当前状态。
- 距基线 4 天；期间仓库设置是否被改过：未知。

## 查询与结果（全部 200，无限流）

运行时刻 `2026-09-21T21:53:06Z` 起，串行、间隔 7 秒。`search_remaining` 由 9 降至 4（第 4 个查询后回升属整分窗口重置，非异常）。

站内搜索组（v0.3 样例原样，含"GitHub"一词）：

- `黄金矿工 GitHub`（zh，名称加用途）：0 个结果。未找到。（基线：0）
- `Gold Miner GitHub`（en，名称加用途）：19 个结果（基线：19），前 5 与基线逐项相同：`xxfu-y/GoldMiner`(2)、`Faithdog/GoldMiner`(0)、`GoldMinerXun/GoldMinerXun.github.io`(0)、`vzhan100/Github-Gold-Miner`(0)、`linhe0x0/gold-miner-github-server`(1)。本仓库不在前 20。未找到。
- `GitHub 跨语言搜索`（zh，用途词）：0 个结果。未找到。（基线：0）
- `GitHub cross-language discovery`（en，用途词）：0 个结果。未找到。（基线：0）
- `跨语言 GitHub 项目发现`（zh，用途词）：0 个结果。未找到。（基线：0）
- `cross-language GitHub project discovery`（en，用途词）：0 个结果。未找到。（基线：0）

站内搜索组（去掉"GitHub"一词）：

- `黄金矿工`（zh，名称）：131 个结果（基线：130）。前 5 仍为黄金矿工游戏（顺序微调）：`fastCreator/cocos-gold`(38)、`qiandingqin/GlodMiner`(45)、`ZhongTaoTian/GoldMiner`(66)、`meishadevs/GoldMiner`(100)、`YangQing-Lin/GoldMiner-LiveServer`(14)。本仓库不在前 20。未找到。
- `gold miner`（en，名称）：1,050 个结果（基线：1,047）。第 1 名仍为 `xitu/gold-miner`（34,348 stars，基线 34,340）。本仓库不在前 20。未找到。

诊断组：

- `gold-miner in:name`：877 个结果（基线：874），第 1 名仍为 `xitu/gold-miner`。

## 解读（只说本轮可比项，不做单一因果结论）

1. 名称词场无变化：中英文名称查询仍被游戏与 `xitu/gold-miner` 占据，本仓库仍不在任何名称查询前 20。裸词未进前 20 不是改名条件（见 0001）。
2. 用途词仍全部 0 结果：词场空白状态延续。但本仓库能否占住用途词取决于简介/topics 是否已填——本次元数据未知，故不能由 0 结果推断“填了就能占住”，也不能推断市场空白。
3. 总数微增（130→131、1047→1050、874→877）是站内语料自然增长量级，不解读为本项目相关信号。
4. 与基线差异不能归因于单一原因：收录时间、排序抖动、语料增长均可能作用；元数据未知则简介因素无法排除也无法确认。

## 未检查

- 仓库元数据（简介/topics/许可证）：未读（核心配额 0）。待配额恢复后补 `GET /repos` 并另起文件记录，不得回填本文件。
- GitHub 网页搜索（登录与未登录、不同地区）：未检查。
- 普通搜索引擎（至少两家、中英文界面各一）：未检查。
- Chrome 商店：不适用。

## 复现

```bash
q() { curl -s "https://api.github.com/search/repositories?q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1")&per_page=20" \
  | jq -c '{total: .total_count, top: [.items[:5][] | {r: .full_name, s: .stargazers_count}], ours: ([.items[] | .full_name] | index("victorzhong0110/gold-miner"))}'; sleep 7; }
q "黄金矿工 GitHub"; q "Gold Miner GitHub"; q "GitHub 跨语言搜索"; q "GitHub cross-language discovery"
q "跨语言 GitHub 项目发现"; q "cross-language GitHub project discovery"; q "黄金矿工"; q "gold miner"; q "gold-miner in:name"
```

未认证搜索配额 10 次／分钟，本轮 9 次查询间隔 7 秒串行；遇 403/429 即停止（本轮未遇到）。
付费调用计数：0。密钥：无。
