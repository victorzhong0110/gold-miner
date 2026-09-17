# W1 交付报告：固定阅读对照、写独立评估材料（首轮第一包）

日期：2026-09-18。分支：`opencode/gui-w1-w8`。依据：[docs/backlog.md](../../docs/backlog.md) W1、[v0.4](../../docs/plan/v0.4.md) W1 与第 10 节。
状态：材料已固定、未运行。本报告不包含任何产品效果结论。

## 1 做了什么

- 固定阅读对照基线 v1：统一中文技术核对阅读语言，现成工具为沉浸式翻译双语对照模式，关键结论回查原文；E1 各组与 E2a A/B 同条件。见 `reading-baseline.md`。
- 固定首轮判定口径 v1：检查窗口（每查询前 30、合并前 30、各组前 5 人工判定、种子命中@30 另算）、逐字段定义与指标边界。见 `judgment-guide.md`。
- 固定运行设置：A/B/C/M/D 预算（1/2/4/4，D 为工具对照）、字段（默认字段主结果、README 配对诊断另行）、排序与成本记账；模型未配置。见 `run-settings.json`（`status: W1-recorded-not-run`，冻结位全为 null）。
- 确认开放题与开发题分离：`queries.yaml` dev 与 eval.batch_1 id 互不重复，eval 覆盖两方向与五类；冻结位仍为 null（运行前冻结）。见已有文件，不在本包修改。
- 种子诊断与开放题分开：新建 `seed-tasks.draft.yaml`（`draft-unfrozen`，`entries: []`，8 个采集位），不等同冻结种子集。
- 固定 E2a 会话设置 v1：两对短会话、单次 10–15 分钟、A/B 顺序平衡、每次最多 3 候选、人工时间单列。见 `../../experiments/E2-open-ended-discovery/session-setup.md`（路径：`experiments/E2-open-ended-discovery/session-setup.md`）。
- 新增可运行检查 `scripts/test_w1_materials.py`（11 项），全套件 70 项通过。

## 2 证据在哪里

- 新建（本分支，未提交即报告路径）：
  - `experiments/E1-cross-language-search/reading-baseline.md`
  - `experiments/E1-cross-language-search/judgment-guide.md`
  - `experiments/E1-cross-language-search/run-settings.json`
  - `experiments/E1-cross-language-search/seed-tasks.draft.yaml`
  - `experiments/E2-open-ended-discovery/session-setup.md`
  - `experiments/E1-cross-language-search/scripts/test_w1_materials.py`
  - `experiments/E1-cross-language-search/W1-report.md`（本文件）
- 复用未改（证据，不算本包产出）：
  - `experiments/E1-cross-language-search/queries.yaml`（dev/eval 分离，`eval_frozen_commit: null`）
  - `experiments/E1-cross-language-search/prompts/`（B/C/D）、`schemas/`（candidates/judgments/seed-set）
  - `experiments/E1-cross-language-search/scripts/github_search.py` 等 1a 脚本与既有测试（59 项通过）
- 运行记录：
  - `python3 experiments/E1-cross-language-search/scripts/test_w1_materials.py` → 11 tests OK。
  - `python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"` → 70 tests OK。
  - 无网络请求；无 GitHub Search 调用；无模型调用。
- 机器可读：`run-settings.json` 为 JSON；候选/判定/种子字段以 `schemas/*.schema.json` 为准。AGENTS.md 第 17 条所指“protocol.md 第 7 节”与当前协议节号不一致（记录格式现为第 5 节），本包以当前协议第 5 节为准，差异已在 `judgment-guide.md` 第 5 节披露。

## 3 失败或未知是什么

- 未运行：E1 首轮检索、人工判定、E2a 会话、E3/E6 调用、E8 复测均未运行。本包任何文件均不得替代运行证据。
- 未冻结：`queries.yaml` eval、`prompts/`、`seed-set`、`run-settings` 的冻结 SHA 全为 null；运行开始前需提交并回填已存在提交 SHA，不把本报告当作冻结提交。
- 未验证：种子仓库存在性、stars、README 语言标签；翻译工具在 GitHub 上的实际版本号与失效模式；英文使用者体验；GitHub 配额与中文查询行为（属 W2）。
- 未检查：GitHub 网页搜索、普通搜索引擎、Chrome 商店（E8 范围，属 W7）。
- 无密钥：本包文件经检查脚本扫描，无 `sk-`/`ghp_`/`github_pat_` 模式；脚本用环境变量 `GITHUB_TOKEN` 等，见 AGENTS.md 第 23 条。

## 4 下一工作包是否具备输入

- W2（候选来源与配额检查）：具备输入。本包的 `run-settings.json` 与 `reading-baseline.md` 已给出字段、预算与排序约束；W2 按 `docs/engineering/prerequisites.md` 第 1 节做小规模默认字段与 README 查询检查，记录失败、限流与无凭据边界。
- W3（最小 E1 脚本与结构化记录）：部分具备。检索与记录侧可用现有 `github_search.py` 加 W2 结论推进；模型部分需 W6 连接配置，未就绪则 W3 模型侧保持待运行。
- W5/W7 可在模型未就绪时先行（见 backlog 说明）：W5 需发起人短会话排期，W7 需名称文案与权限确认；本包的 `session-setup.md` 与决策 0001 文案已可作为其输入。
- W4/W6/W8：未运行，不具备产出条件。W4 需 W3 与冻结材料；W6 请求部分需本地个人配置；W8 需 W4/W5。
- 本次未改 `docs/backlog.md` 勾选与 `docs/plan/v0.3.md`；待提交后由维护者在 backlog 记录本报告路径。
