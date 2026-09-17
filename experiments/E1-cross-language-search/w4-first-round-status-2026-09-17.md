# W4 E1 首轮及 E9 诊断状态（2026-09-17，未运行）

对应：`docs/backlog.md` W4、`docs/plan/v0.4.md` W4 与第 5 节 E1/E9 行、E1 协议第 2–7 节、E9 `README.md`。
状态：未运行。未创建 `runs/<日期>-<标签>/`（遵守 `runs/README.md`：没有真实运行不建日期目录）。

## 1 做了什么

- 核对首轮输入是否齐备，未发起任何评估检索与判定：
  - 开放任务：`queries.yaml` eval.batch_1（20 条，两方向、五类覆盖）已写但 `eval_frozen_commit: null`，冻结提交待定。
  - 已知目标诊断：`seed-tasks.draft.yaml` 为 `draft-unfrozen`，`entries: []`，`repo/stars` 全 `null`，未达到 `schemas/seed-set.schema.json` 的冻结条件。
  - 方法与预算：`run-settings.json` 为 `unfrozen-no-run`，A/B/C/M 预算与字段已记录；`model.concrete_model_id: null`，C/M 查询生成无可用模型。
  - 脚本：W3 `e1_minimal_runner.py` 已就绪（80 tests OK），但无运行清单、无 `materials_commit`。
- E9：`terms.yaml` 40 条概念为未验证候选表达；纯词表/纯 AI/混合三组比较需要 E1 冻结题集加配平字段、预算、排序，且 B/C 组需同一模型。模型未配置，故 E9 未展开。

## 2 证据在哪里

- 输入核对命令（均本地、无网络、无凭据）：
  - `python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"` → 80 tests OK（含 W1 11 项、W3 10 项）。
  - `python3 -c "import json; print(json.load(open('experiments/E1-cross-language-search/run-settings.json'))['freeze'])"` → `eval_frozen_commit null` 等未冻结标记。
- 无 `candidates.jsonl`、`judgments.jsonl`、运行报告产生；这是如实缺失，不是遗漏。

## 3 失败或未知是什么

- 失败：无（未运行，无失败可计）。
- 未知/阻塞：
  - 冻结提交 SHA 待 W1 材料提交后填入运行清单（不要求文件包含自身 SHA，见协议第 2 节）。
  - 无凭据搜索配额緊（W2：搜索 10 次/分，核心 `remaining 4`；W7 复测遇 403）。全量 20 任务 × A/B/C/M 必须分批串行，否则必触发限流。
  - C/M 查询生成与 D 强对照需要可用模型与费用边界（见 W6），当前 `OPENAI_*`、`GITHUB_TOKEN` 均未设置。
  - 判定需要人工核对（各组前 5），耗时按候选量另计，尚未安排。

## 4 下一工作包是否具备输入

- W5 具备输入（E2a 不依赖 E1 成功，`session-setup.md` 已固定，只等发起人短会话）。
- W6 部分具备输入（公开片段基线可做，模型探测需本地个人配置）。
- W4 进入运行的条件：种子集冻结、提示词/词表冻结提交、运行说明提交、模型或纯词表路径二选一就绪。任一缺失都不得启动评估检索。
