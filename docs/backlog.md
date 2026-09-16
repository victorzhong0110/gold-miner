# 待办与 issue 草稿

整理日期：2026-09-17。每条可直接开成 issue：标题即 issue 标题，正文抄"内容"，加"标签"，在正文末写"依赖"。建议标签：`decision`、`repo`、`experiment`、`hypothesis`、`engineering`、`phase:1a`、`phase:1b`、`blocked`。

顺序原则：先决策，再仓库整理，再 1a 实验；1b 工程项全部依赖 E1 首轮结论。

## 决策

### D1 决定项目名称
- 内容：按 [决策 0001](decisions/0001-project-name.md) 选项与检查步骤，给出最终名称并回填决定。
- 标签：`decision`
- 依赖：无。阻塞 R1、X6，以及任何公开引用。

### D2 决定许可证
- 内容：按 [决策 0003](decisions/0003-license.md) 决定代码与文档许可。
- 标签：`decision`
- 依赖：无。阻塞 R2。

### D3 决定切入方向
- 内容：中英双向并列，还是先选一个方向。依据 [评审 3.4](reviews/2026-09-17-v0.3-review.md) 与 X1 的 H0 结果。写进 v0.4 第 1 节。
- 标签：`decision`、`hypothesis`
- 依赖：X1。

### D4 确认模型接入配置
- 内容：确认 [决策 0002](decisions/0002-model-endpoint-config.md)；MiniMax 降为首个预设。
- 标签：`decision`
- 依赖：无。阻塞 X5 的模型调用部分与 G3。

## 仓库整理

### R1 填写仓库简介与 topics
- 内容：用 [决策 0001 附录](decisions/0001-project-name.md) 文案，替换名称后填写。
- 标签：`repo`
- 依赖：D1。

### R2 添加 LICENSE
- 内容：按 D2 结果加 `LICENSE`，必要时加 `NOTICE`；README 边界一节加许可说明。
- 标签：`repo`
- 依赖：D2。

### R3 v0.1、v0.2 计划入库或删除引用
- 内容：v0.3 第 1 节引用 0.2 版；仓库无 0.1、0.2。补进 `docs/plan/` 或在 v0.4 删引用。
- 标签：`repo`

### R4 演示站点与预选材料入库或注明私有
- 内容：v0.3 提到的演示站点、22 个预选仓库、20 道开发题不在仓库。能公开的放 `docs/` 或 `experiments/`，标"不作为效果证据"；不能公开的注明私有与原因。
- 标签：`repo`

### R5 起草 v0.4 计划
- 内容：按 [评审第 7 节](reviews/2026-09-17-v0.3-review.md) 清单逐条落实，另起 `docs/plan/v0.4.md`，不改 v0.3。
- 标签：`repo`
- 依赖：D1、D3、D4。

## 1a 实验（不写扩展）

### X1 H0 规模测量：README 仅中文的仓库有多少
- 内容：按 [E1 协议第 2 节](../experiments/E1-cross-language-search/protocol.md) 抽样、分类、报告；含仅中文仓库中带英文简介／topics 的比例。
- 标签：`experiment`、`hypothesis`、`phase:1a`
- 依赖：GitHub PAT。

### X2 站内中文搜索前置探测
- 内容：按 [工程前置第 2 节](engineering/prerequisites.md) 用 10 个仓库、20 个短语测 `in:readme` 与默认搜索召回；结论写回 E1 协议第 4 节。
- 标签：`experiment`、`phase:1a`
- 依赖：X1 顺手产出的仅中文仓库。

### X3 构造并冻结 held-out 种子集
- 内容：按 [E1 协议第 3 节](../experiments/E1-cross-language-search/protocol.md) 从 HelloGitHub 月刊抽样两方向种子，写查询，提交 `seed-set.jsonl`。
- 标签：`experiment`、`phase:1a`
- 依赖：X1 的分类器。

### X4 预注册 E1 评估集与提示词
- 内容：填 `queries.yaml` 的 `eval.batch_1`（≥ 20 条，两方向五类），提交 `prompts/`，回填 `preregistration` 的 SHA；发起人确认协议第 9 节阈值。
- 标签：`experiment`、`phase:1a`
- 依赖：无（可与 X1–X3 并行）。

### X5 E1 首轮：1a 脚本、运行、报告
- 内容：实现四组方法与记录字段（协议第 5、7 节），跑 dev 后跑 eval 与种子集，写 `runs/<日期>-e1-round1/report.md`，按第 9 节给出继续／缩小／暂停。
- 标签：`experiment`、`hypothesis`、`phase:1a`
- 依赖：X2、X3、X4、D4。

### X6 E8 重跑
- 内容：D1、R1 完成后按 [模板](../experiments/E8-discoverability/template.md) 重跑，补网页搜索与两家搜索引擎。
- 标签：`experiment`
- 依赖：D1、R1。

### X7 E9 词表／AI／混合
- 内容：复用 E1 种子集与记录字段，比较三种查询处理（[研究记录](research/ehviewer-cross-language-search.md)）。
- 标签：`experiment`
- 依赖：X5 结论为继续或缩小。

## 1b 及以后（全部依赖 X5 结论为"继续"）

### G1 GitHub 凭据支持与无凭据降级
- 内容：细粒度 PAT 配置；未配置时只做原生加一条译词查询并提示。[工程前置第 1 节](engineering/prerequisites.md)。
- 标签：`engineering`、`phase:1b`、`blocked`

### G2 GitHub 导航事件与锚点实测
- 内容：确认当前 Turbo 事件名、仓库页 README 与 issue 评论的稳定锚点，写守卫。[工程前置第 3 节](engineering/prerequisites.md)。
- 标签：`engineering`、`phase:1b`、`blocked`

### G3 MV3 骨架
- 内容：service worker 队列落存储、IndexedDB 缓存、`optional_host_permissions`、Port 逐段推送。[工程前置第 4–6 节](engineering/prerequisites.md)、[决策 0002](decisions/0002-model-endpoint-config.md)。
- 标签：`engineering`、`phase:1b`、`blocked`
- 依赖：D4。

### G4 密钥边界测试
- 内容：[工程前置第 7 节](engineering/prerequisites.md) 的 DOM、日志、导出扫描测试。
- 标签：`engineering`、`phase:1b`、`blocked`

### G5 Ollama 本地预设实测
- 内容：扩展来源请求 Ollama 的 origin 校验与 `OLLAMA_ORIGINS` 设置，写进安装说明。
- 标签：`engineering`、`phase:1b`、`blocked`

### 其余实验与命题
- E2／H2 无目标发现、E3／H4 忠实翻译（对照改为沉浸式翻译双语模式）、E4／H3 自然度、E5／H5 译文复用、E6／H6 自备 API、E7 持续使用、H7 双向、H8 零补贴：各开一条占位 issue，标 `blocked`，正文链接 v0.3 对应章节与 [评审 3.5](reviews/2026-09-17-v0.3-review.md) 的对照组要求。进入 1b 后再拆任务。

## 已完成（2026-09-17）

- README 缩为入口页；v0.3 原文迁至 `docs/plan/v0.3.md`。
- 新增 `README.en.md`。
- 新增评审、决策 0001–0003、工程前置、E1 协议与 dev 任务集、E8 首次探测与模板、本文。
