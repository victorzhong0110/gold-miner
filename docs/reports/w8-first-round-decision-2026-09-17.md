# W8 首轮投入决策报告（2026-09-17，基于 W1–W7 实际证据）

对应：`docs/backlog.md` W8、`docs/plan/v0.4.md` 第 7 节（分支）与第 8–9 节（待定/暂缓）。
性质：过程决策记录，不是产品效果结论。本轮零检索运行、零会话、零付费调用；下述“继续”均指下一笔小投入，不证明普遍有效。

## 1 各工作包四项（做了什么；证据；失败/未知；下一输入）

| ID | 做了什么 | 证据在哪里 | 失败或未知 | 下一输入是否具备 |
|---|---|---|---|---|
| W1 | 固定阅读基线 v1、判定口径 v1、运行设置、种子草案（8 采集位，entries 空）、E2a 会话设置；开放题与开发题分离确认 | `experiments/E1-cross-language-search/W1-report.md`；`reading-baseline.md`、`judgment-guide.md`、`run-settings.json`（unfrozen-no-run）、`seed-tasks.draft.yaml`（draft-unfrozen）、`experiments/E2-open-ended-discovery/session-setup.md`、`scripts/test_w1_materials.py`（11 项）；全套件 70 OK（当时） | 未运行、未冻结（SHA 全 null）、种子/工具版本/配额未验证；密钥扫描无命中 | W2 具备；W3 部分具备；W5/W7 可先行 |
| W2 | 无凭据串行诊断 4 请求（rate_limit＋默认/显式 README/中文短语各 1），间隔 5 秒 | `experiments/E1-cross-language-search/w2-source-check-2026-09-17.md`（真实 total_count/top3/配额头；中文查询串与 eval-01 重合已披露为诊断非运行） | 0 失败；搜索 10 次/分、核心 remaining 4；README 组 text_matches 空记 unknown；中文有结果≠空间可检索 | W3 具备（须分批退避） |
| W3 | 最小 Runner（A/B/C/M 预算 1/2/4/4、合并去重截断 30、来源保存、取消与逐变体错误记录；D 拒绝执行）＋ 10 项单测 | `experiments/E1-cross-language-search/scripts/e1_minimal_runner.py`、`scripts/test_e1_minimal_runner.py`；全套件 80 OK | 模型侧未就绪；Runner 无真实运行记录 | W4 运行清单待冻结 SHA 与模型/词表二选一 |
| W4 | 仅核对输入，未启动 E1/E9 | `experiments/E1-cross-language-search/w4-first-round-status-2026-09-17.md`；未建 `runs/<日期>-*/` | 未运行；种子空、模型 null、冻结 null；全量需分批 | W5 可先行；W4 待种子冻结＋运行说明 |
| W5 | 沿用会话设置 v1，未开展会话 | `experiments/E2-open-ended-discovery/session-setup.md`（未运行）＋ test 断言 | 无参与者/起点/候选/反馈/耗时；英文体验缺席即未验证 | 需发起人两对短会话排期 |
| W6 | 本地分类器冒烟（3 文件真实输出）＋环境检查（四变量全 False）；E3 缺口与模型探测未运行 | `docs/reports/w6-baseline-connectivity-2026-09-17.md`；80 tests OK | 翻译缺口、端点/余额/延迟全未知；零费用 | W3 模型侧仍阻塞；决策约束零补贴明确 |
| W7 | 复用简介/topics 草案与许可备选；E8 API 复测 2 次均 403；网页/外部未检查 | `docs/reports/w7-metadata-e8-prep-2026-09-17.md`；0001/0003；基线探测定稿保留 | 当前元数据状态未知；复测未完成 | W14 不具备；待配额恢复后新日期文件重跑 |
| W8 | 本报告 | 本文件 | 小样本偏差（熟悉效应、选择偏差、非盲）待运行时披露 | 下一步见第 2–3 节 |

测试总览：`python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"` → 80 tests OK（59 既有＋W1 11＋W3 10）。Live 探测不可重复断言，仅作证据记录。

## 2 分方向与分功能决策（对照 v0.4 第 7 节）

- 主动搜索（E1）：无可复核增益证据（未运行）→ 不进入 W9–W10 的搜索投入；**窄化**为只完成冻结（SHA 回填运行清单）＋种子集补齐（多来源、含低热度、stars≥50、语言标签）＋分批诊断。C 与 B、M 与 C 的比较规则不变；字段不一致先修实验不作结论。
- 无目标发现（E2）：E2a 无具体价值案例 → **暂停**自动候选与排序（W9）与扩展开发（W10）；**继续**最小动作仅为等发起人两对短会话（W5）。人工有用≠自动有效，届时再定 W9。
- 翻译阅读（E3/E6）：现成翻译是否足够未知 → **继续**片段缺口检查（固定公开片段集＋工具版本记录），**暂停**自建翻译比较、长篇缓存、公共代理。模型保持 BYOK、可替换边界；未知余额显示未知。
- 工程与交付：Chrome 扩展（W10/W11）、本地复用（W12）、持续试用（W13）、试用包（W14）全部**暂停**——既无效果证据，也不满足 AGENTS.md H1 门槛。暂缓清单（独立站、全量索引、大模型训练、实时平台、商店上架、商业化）维持不动。
- 可发现性（E8）：名称沿用（0001），简介/topics 待权限应用后复测；裸词不争第一，名称加用途与纯用途双入口按模板验收。

## 3 未验证项与下一步最小动作

1. 冻结提交：将本轮新增文件提交后，把已存在提交 SHA 回填运行清单（queries eval/prompts/seed/run-settings），运行后不改本批。
2. 种子集：按 `schemas/seed-set.schema.json` 补 8 条（多来源、HelloGitHub 仅线索之一、低热度），开放题作者不先看答案。
3. W5：发起人确认两对短会话起点与时间；会话记录含全部展示/略过候选与人工耗时。
4. E3 片段集：固定少量公开片段（两方向、术语/否定/限制/代码/讨论），再做现成工具对照。
5. E8：配额恢复后新日期文件重跑三入口，互链 0001。
6. 模型：个人本地配置就绪后才做最小连接探测（0002 第 3 节），记录格式/延迟/用量/错误分类；密钥永不进仓库。

## 4 本轮变更路径（AGENTS.md 第 18 条：先列出将改路径）

- 新增（未改既有文件，未动 `docs/backlog.md` 勾选、`docs/plan/v0.3.md`、`LICENSE`、仓库名、扩展代码）：
  - `experiments/E1-cross-language-search/w2-source-check-2026-09-17.md`
  - `experiments/E1-cross-language-search/scripts/e1_minimal_runner.py`
  - `experiments/E1-cross-language-search/scripts/test_e1_minimal_runner.py`
  - `experiments/E1-cross-language-search/w4-first-round-status-2026-09-17.md`
  - `docs/reports/w6-baseline-connectivity-2026-09-17.md`
  - `docs/reports/w7-metadata-e8-prep-2026-09-17.md`
  - `docs/reports/w8-first-round-decision-2026-09-17.md`（本文件）
- 沿用（此前已在工作区、未提交，本轮未改内容，只复核）：`W1-report.md`、`reading-baseline.md`、`judgment-guide.md`、`run-settings.json`、`seed-tasks.draft.yaml`、`session-setup.md`、`scripts/test_w1_materials.py`。
- 未运行项全部标“未运行”，未用计划文档或模拟成功替代证据；未编造 GitHub 结果、H0/E1 指标、API 额度、用户反馈。

## 5 追记 2026-09-18（W6/E3 证据更新，不改 §§1–4 本轮记录）

将改路径（AGENTS.md 第 18 条）：`docs/reports/w8-first-round-decision-2026-09-17.md`（本追记 only）、
`docs/backlog.md`（W8 行 only）、`experiments/E8-discoverability/` 下新日期文件（如配额允许则新建，否则不建）。
不改 `docs/plan/v0.3.md`、仓库名、`LICENSE`、扩展代码；只改任务指定文件。

- W6/E3 行刷新（§1 W6 行的后续状态，不重写原文）：
  - 片段已冻结：`experiments/E3-faithful-reading/fragments-2026-09-17.md`，
    `materials_commit: 2be593765150adb15b92c2093505d48ecbcf769a`（`git cat-file -e` 存在性已核验；
    冻结语义为片段出处冻结，故意不跟随 HEAD，见该文件第 0 节与 `test_fragments.py`）。
  - 对照协议已落地：`experiments/E3-faithful-reading/translation-contrast-2026-09-18.md`
   （含工具/版本/设置/语言对/原文可见/失败记录协议、逐片段源风险笔记、全 `未运行` 观察模板）。
  - 对照输出仍未运行：翻译输出与判定列全 `未运行`；工具版本、浏览器版本、设置、等待与费用全未知；
    零请求、零费用；未点 Subscribe/Go；无密钥。
  - 个人模型探测仍阻塞：本地无个人配置，最小连接探测未发生；W4 评估检索、W5 短会话均未发生，
    本追记不替代其中任何一项证据。
- §3 下一步最小动作刷新（只标注增量，不重写 §3）：
  - §3-1（冻结回填）：仍未做。`queries.yaml` 的 `eval_frozen_commit`、`run-settings.json` 的 `freeze.*` 保持 `null`；
    种子与模型均未就绪，回填即虚假冻结。
  - §3-2（种子集）：仍未做。`seed-tasks.draft.yaml` 仍 `draft-unfrozen` 且 `entries: []`。
  - §3-3（W5）：仍阻塞，需发起人两对短会话排期；本次无会话发生。
  - §3-4（E3 片段集）：部分完成——片段冻结与对照协议已完成，对照输出待运行（运行者在新日期文件记录实测值，不得回填旧文件）。
  - §3-5（E8）：2026-09-18 已复测 1 次即遇限流停止，见 `experiments/E8-discoverability/2026-09-18-retest.md`
   （`GET /repos` 403，核心 `remaining 0/60`，搜索查询未发起）；基线仍为 `experiments/E8-discoverability/2026-09-17-probe.md`。
  - §3-6（模型）：仍阻塞，需个人本地配置就绪后才做最小连接探测；密钥永不进仓库。
- 决策结论不变：§2 分方向/分功能处置维持原样；本追记只刷新证据指针，不产生新的效果结论。
  本轮仍零检索运行、零会话、零付费调用；未编造 GitHub 结果、H0 占比、E1 指标、API 额度。
