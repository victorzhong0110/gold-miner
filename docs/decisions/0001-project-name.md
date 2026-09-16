# 0001 项目名称

状态：待决策（发起人）  
提出日期：2026-09-17  
截止建议：进入第 1b 阶段（扩展开发）之前；最好在把 backlog 开成 issues 之前，避免公开引用旧名。

## 背景

v0.3 第 11 节要求项目能被不同语言用户直接搜到，并以"名称加用途应找到官方入口"为 E8 验收。2026-09-17 的首次探测（[记录](../../experiments/E8-discoverability/2026-09-17-probe.md)）显示两种语言的名称都已被占：

- 英文：`gold miner` 在 GitHub 有 1,047 个结果，第一名 [xitu/gold-miner](https://github.com/xitu/gold-miner)，34,340 stars，是"掘金翻译计划"——同名且同为翻译类项目。`gold-miner in:name` 874 个。
- 中文：`黄金矿工` 130 个结果，前 8 名全部是黄金矿工游戏。
- 本仓库在上述任何一条查询的前 20 名中都没有出现。

这是词场被占，不是排名可以追上的差距。改名的沉没成本现在为零：没有代码、没有公开引用、没有商店页面。

## 选项

### A 改名（建议）

选择一个在 GitHub 上近乎空白、两种语言都不与知名事物冲突的名称。满足以下全部条件再定：

1. `NAME in:name` 在 GitHub 返回 0 个结果，或只有 stars 低于 100 且非同赛道的仓库。
2. 网页搜索 `NAME github` 前 10 名没有其他软件项目占据。
3. 中文名不是知名游戏、影视、品牌或成语常用义；英文名不是常见普通名词组合。
4. 中英文名能互相对应（同义或音义结合），简介开头能同时出现两种名称。
5. 仓库 slug 与英文名一致；不要求域名。
6. 若以后上架 Chrome 商店，届时再查商店名称占用；本轮不作为条件。

检查步骤（每个候选约 2 分钟）：

```bash
q() { curl -s "https://api.github.com/search/repositories?q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1")&per_page=10" \
  | jq -c '{total: .total_count, top: [.items[:5][] | {r: .full_name, s: .stargazers_count, d: .description}]}'; }
q "候选名 in:name"
q "候选名"
q "候选中文名"
```

结果按 [E8 模板](../../experiments/E8-discoverability/template.md) 记入一次探测文件，改名后重跑一次作为对照。

### B 保留名称，靠副标题、简介与 topics

名称查询注定输给 xitu 与游戏；只能争取用途词查询（目前 0 个结果，容易占住）。等价于放弃 E8 的"名称加用途"验收，需要在 v0.4 第 11 节明确写出这一让步。

### C 保留中文昵称，换英文标识

中英文都已被占（见背景），此项只解决一半，不建议。

## 决定

（待填写：选项、最终名称、日期、依据的探测文件路径。）

## 决定后要做的事

- 仓库改名（GitHub 会为旧地址保留跳转）。
- 填写简介与 topics（附录文案，替换名称后使用）。
- 全仓库替换名称；v0.3 原文保留旧名并在文首注明。
- 重跑 E8，记录文件与本决策互链。

## 附录：简介与 topics 文案

简介（GitHub 限 350 字符，两种语言各一句，名称在句首）：

```
{中文名}：用你自己的语言发现、阅读、探索 GitHub 项目的 Chrome 扩展（规划中，中英双向）。{English name}: discover, read and explore GitHub projects in your own language; Chrome extension, zh/en first, planning stage.
```

topics（小写，最多 20 个，先放真实相关的）：

```
chrome-extension browser-extension github cross-language cross-lingual-search
project-discovery readme-translation translation chinese english llm bring-your-own-key
```

"规划中／planning stage"在有可安装版本后删去。
