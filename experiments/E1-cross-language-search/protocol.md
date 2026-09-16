# E1 跨语言搜索：脚本先行的验证协议

状态：协议草案，2026-09-17。运行前发起人确认第 9 节阈值并提交 `queries.yaml` 的评估集。  
对应：v0.3 第 3、5、6、9 节；[评审 3.1–3.3、3.5、3.6](../../docs/reviews/2026-09-17-v0.3-review.md)；[工程前置第 1、2 节](../../docs/engineering/prerequisites.md)。

## 0 要回答的问题

- H1：固定需求下，语言是否造成遗漏——是否存在原语言路径漏掉、另一语言路径找到、且确实合适的仓库。
- H0（新增）：README 仅中文的仓库规模是否足以支撑 en→zh 方向；以及这些仓库里有多少其实带英文简介或 topics、用英文默认搜索本来就能找到。

H1 决定产品独有价值；H0 决定 H1 值不值得验。两者都不需要 Chrome 扩展。

## 1 范围

第 1a 阶段：一个命令行脚本加人工判定。脚本做查询改写、调用 GitHub Search API、合并去重、写结构化记录；人做适合度判定。不做页面注入、不做翻译缓存。

不在范围：无目标推荐（E2）、翻译质量（E3）、自然度（E4）。这些依赖扩展。

## 2 H0 规模测量（约半天）

抽样：

- star 区间：`100..199`、`200..499`、`500..999`、`1000..4999`、`>=5000`。每区间用 Search API 取 200 个仓库。Search API 单查询上限 1,000 条且默认按相关度排，抽样用 `sort=updated` 随机取页并记录页号，偏向近期活跃仓库；写进报告的局限里。
- 排除 fork、archived。
- 每个仓库取 README 原文（`GET /repos/{owner}/{repo}/readme`，raw），记录 blob SHA、简介、topics。

分类（启发式，记录版本号）：

- 预处理：去代码块、URL、HTML 标签、徽章行；取前 3,000 字符。
- CJK 占比 = 中日韩表意字符数 ÷（中日韩表意字符数 + 拉丁字母数）。含日文假名判为 ja，含韩文判为 ko，均不计入 zh。
- 仅中文：占比 ≥ 0.6，且仓库根目录无 `README.en.md`、`README_EN.md`、`README-en.md` 等英文副本。双语：0.2–0.6，或存在英文副本。英文：< 0.2。
- 人工抽 30 个核对分类准确率，写进报告。

报告字段：各区间仅中文／双语／英文占比；仅中文仓库中简介为英文的比例、topics 非空的比例；ja、ko 数量另列。

判定：仅中文仓库在 stars ≥ 500 区间占比低于 3%，且其中多数带英文简介，则 en→zh 方向的检索缺口小，H1 只在 zh→en 方向继续；把这个结论写进 v0.4 第 1 节的方向决定。阈值为建议，运行前确认。

## 3 held-out 种子集构造

来源：HelloGitHub 月刊（[521xueweihan/HelloGitHub](https://github.com/521xueweihan/HelloGitHub)），每期用中文一段介绍若干开源项目，同时包含中文项目与英文项目。它独立于本项目的 22 个预选仓库与开发题，且介绍文字是现成的"用户需求描述"。

步骤：

1. 取最近 6 期月刊 Markdown，解析每条目的仓库地址与中文介绍。
2. 核对仓库存在、非 fork、非 archived、stars ≥ 50。
3. 用第 2 节的分类器标 README 语言。
4. 分两组：目标为"仅中文 README"的仓库进 `en2zh` 组（英文使用者要找中文项目）；目标为"英文 README"的仓库进 `zh2en` 组（中文使用者要找英文项目）。每组随机取 25–40 条。
5. 为每条写查询：`zh2en` 组直接从中文介绍提炼 1 条中文需求句（不抄仓库名、不抄英文词）；`en2zh` 组由写查询者只看中文介绍的机器译文写 1 条英文需求句，不看仓库页。写查询者知道介绍、不知道仓库排名，记录这一偏差。
6. 冻结：`seed-set.jsonl` 提交到仓库；运行报告写明提交 SHA。冻结后不增删，只允许标记"仓库已消失"。

字段：`seed_id, direction, repo, stars, readme_lang, hellogithub_issue, zh_description, query, query_lang, frozen_at`。

种子集只用于评估，不用于调提示词、词表或排序。开发用 `queries.yaml` 的 dev 组。

## 4 站内中文搜索前置探测

按 [工程前置第 2 节](../../docs/engineering/prerequisites.md) 执行，结果写 `runs/<日期>-cjk-probe/report.md`。结论决定第 5 节 C 组是否启用 `in:readme` 变体，以及是否需要补充候选来源。

## 5 方法组

四组，同一任务、同一候选检查预算：

- A 原生：用户原始查询，GitHub 默认搜索（名称、简介、topics），取前 30。
- B 译词：把原始查询整体翻成另一语言各 1 条（固定提示词或词表），两条查询各取前 30，合并去重。这是"简单译词搜索"对照，也是 E9 的纯词表组雏形。
- C 本方案（1a 脚本）：模型按固定提示词把需求改写为最多 2 条中文加 2 条英文查询，允许同义用途词与 GitHub 语法；结果少于 10 条时追加 1 条 `in:readme` 变体（取决于第 4 节结论）。合并去重到规范仓库，排序规则固定并写进报告（建议：命中变体数降序、其次 stars）。取前 30。
- D 强对照：支持联网的通用 AI 助手，同一查询，请它列出 GitHub 仓库，限时 5 分钟。记录它给出的仓库并逐个核实存在；不存在的计为幻觉。

预算：B、C 每任务最多 5 次 Search API 调用；模型调用每任务最多 2 次；A 1 次。所有组的人工检查预算相同：前 10 名每条最多 1 分钟。

改写提示词、词表与排序规则在运行评估集前提交到仓库，运行中不改。

## 6 任务集与预注册

- dev 组：≤ 10 条，用于写脚本与调提示词，可随时改。
- eval 组：≥ 20 条开放任务（无已知目标，靠判定），加第 3 节种子集（有已知目标，算召回）。覆盖两方向与五类：高频术语、未收录词、多义词、否定条件、长需求。每类每方向至少 2 条。
- 预注册：eval 组写进 `queries.yaml` 并提交，提交 SHA 写进运行报告；运行开始后不改 eval 组。结果不理想时可新增 eval 组第二批，但第一批结果必须原样保留并报告。

## 7 记录字段

每次运行写 `runs/<日期>-<标签>/candidates.jsonl` 与 `judgments.jsonl`，一行一条：

candidates：`run_id, task_id, direction, arm, variant_query, variant_lang, api_query, page, rank, repo, stars, matched_fields, readme_lang, is_seed_target, fetched_at`

- `matched_fields` 来自 `text-match` 响应，记录命中名称／简介／README，没有则记 `unknown`。
- `readme_lang` 用第 2 节分类器，只对进入前 10 的候选计算，节省核心 API 配额。

judgments：`run_id, task_id, repo, purpose_fit (yes|partial|no), hard_conditions (satisfied|conflict|unknown), kind (tool|library|tutorial|list|mirror|other), novel_to_judge (yes|no), judge, judged_at, notes`

判定时把各组前 10 合并去重、隐藏组别，逐条判定后再回填到组。第二次看到同一仓库时的速度不算优势（v0.3 第 5 节）。

## 8 指标

分方向分别报告，不合并：

- 种子召回@30：每组找回的种子目标比例。这是召回下限，种子只是相关仓库的一个样本。
- 独有合适发现：`purpose_fit = yes` 且 `kind ∈ {tool, library}`，只被某一组找到的仓库数；每组都列，双方独有的好结果都保留。
- 前 10 判定精度：前 10 中 `purpose_fit = yes` 的比例。
- 硬条件误判：`hard_conditions = conflict` 却排进前 10 的数量。
- 成本：每任务 Search API 次数、模型调用次数、总耗时。
- D 组幻觉率：不存在仓库数 ÷ 给出仓库数。

不声称总体召回率；不用模型自评分替代人工判定。

## 9 判定规则（建议阈值，运行前确认）

- 继续 H1：某一方向上 C 的种子召回比 A 高 0.15 以上，且开放任务中 C 的独有合适发现 ≥ 3，且 C 的前 10 精度不低于 A 超过 0.10。
- 缩小到译词：C 与 B 的种子召回差 ≤ 0.05 且独有发现数相近。说明增益来自术语翻译本身；实现 B（词表加一次改写），不做多变体流水线。这与 E9 的比较结果合并解读。
- 暂停 H1：两方向 C 都不高于 A，或增益只在 dev 组出现。保留记录，回到 v0.3 第 6 节"暂停或改方向"。
- D 组若在相同预算下整体不差于 C，写明"强对照已同样好用"，进入 v0.3 的暂停条件讨论。

## 10 公平条件

- 四组同一天、同一账号、同一网络运行；Search API 结果随时间变化，记录 `fetched_at`。
- 候选检查预算、前 K、判定人一致；判定盲组。
- A 只有 1 次调用不是不公平：它模拟用户实际行为；C 多出的调用计入成本指标。

## 11 输出物

```
experiments/E1-cross-language-search/
  protocol.md                 本文
  queries.yaml                dev 组、eval 组、预注册信息
  seed-set.jsonl              冻结后提交
  prompts/                    改写与译词提示词，运行前提交
  scripts/                    1a 脚本；语言与依赖由实现者定，README 写清运行方式与所需环境变量（GITHUB_TOKEN、模型三元组）
  runs/<日期>-<标签>/
    candidates.jsonl
    judgments.jsonl
    report.md                 数据、指标、局限、按第 9 节的判定，以及漏掉的好结果
```

报告同时列支持与反驳方案的案例（v0.3 第 10 节）。

## 12 与 E9 的关系

E9 比较纯词表、纯 AI、词表加 AI 三种查询处理。本协议的 B 组接近 E9 的 A 组，C 组接近 E9 的 B 组。1a 完成后，如进入 E9，复用本协议的种子集、记录字段与指标，只替换第 5 节的查询处理方式。
