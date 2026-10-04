# 2026-10-05：盲判记录与仓库自己的 judgments schema 不兼容

判定材料即将由发起人判定。核对「判定人会产出什么形状的记录」时发现：
**盲判步骤产出的记录，无法通过仓库自己定义的 `judgments.schema.json`。**
而 `judgment-guide.md:41` 写明「判定记录字段以本文件加 schemas 为准」。

## 1. 三方字段集不一致

机械提取三处（不是靠读散文推断）：

| 来源 | 字段 |
|---|---|
| `judgments.schema.json`（required，additionalProperties: false） | `hard_conditions, judge, judged_at, kind, notes, novel_to_judge, purpose_fit, reason, repo, run_id, task_id, worth_following` |
| `blind-sheet.md`（「每项记录…」） | `blind_id, purpose_fit, hard_conditions, kind, novel_to_judge, worth_following, reason, judge, judged_at, notes` |
| `blind_eval.analyze` 实际读取 | `blind_id, judge, judged_at, novel_to_judge, reason` + 校验用的 `purpose_fit, hard_conditions, worth_following` |

差异恰好两边对称：

- 判定表和 `analyze` 有 **`blind_id`**，而 **schema 没有**
  → `additionalProperties: false` 会直接拒绝
- schema 必填 **`run_id` / `task_id` / `repo`**，而盲判记录**不产出**
  → 必填校验不通过

于是：**发起人按判定表认真填完，得到的记录无法通过仓库唯一声明权威的 schema。**
下游要么校验失败，要么绕过校验——两种都不好。

## 2. 为什么两边会不一样（不是谁写错了）

- `judgments.schema.json` 描述的是**回填后**的记录：有 `run_id`、`task_id`、`repo`
  （非盲判定天然知道这些，`2026-09-22-w4-first` 的 45 行就是这个形状，schema 校验通过）
- 盲判阶段判定人**只知道 `blind_id`**，来源组被刻意遮蔽，所以按 `blind_id` 记录

两种形状都合理，缺的是**把它们接起来的桥**。之前没有。

## 3. 修法

### 3.1 新增盲判输入 schema

`schemas/judgments-blind.schema.json`：描述盲判输入的真实形状
（`blind_id` + 判定表要求的 10 个字段），同样 `additionalProperties: false`。
它的 `description` 写明了与 `judgments.schema.json` 的分工和此前的不兼容。

### 3.2 新增导出，把盲判记录回填成合法记录

`blind_eval.export_judgments(key, judgments, judge_kind)`：

- `run_id` / `task_id` / `repo` **从 `blind-key.json` 取**，不是编造
  ——key 本来就记录了每个 `blind_id` 对应的 task 与 repo
- 导出形状与 `judgments.schema.json` 一致（每行一个 run/task/repo）
- **不写 arm**：arm 留在 `groups` 里供分析用，不进入记录
- `kind` / `notes` 若缺失则**拒绝导出**，不填默认值
  ——`analyze` 不读这两个字段，但 schema 必填；替判定人填值等于伪造他的判断

实测导出 3 行，全部通过 `judgments.schema.json` 校验，且 `arm` 未泄漏。

### 3.3 三方漂移棘轮

`test_blind_eval.py` 新增 7 项，把三方锁在一起：

- 判定表记录的字段集 **必须等于** 盲判 schema 的 required
- `analyze` 读取的每个字段，盲判 schema 都必须有描述
- 显式断言「盲判行确实无法满足非盲 schema」（把不兼容写在测试里，不只是暗示）
- 导出记录通过 schema 校验、身份字段来自 key、不含 arm、缺 `kind`/`notes` 时拒绝

棘轮双向验证：临时从判定表删掉 `kind` → `test_sheet_documents_exactly_the_blind_schema_fields` 失败；还原 → 27/27 通过。
**下一批次若判定表字段变了，测试会立刻失败**，逼着同步 schema，而不是让三方悄悄漂移。

## 4. 没有改判定材料

`blind-sheet.md` 与 `2026-10-04-minimax/` 下的材料**一字未改**
（棘轮验证时的临时改动已还原，`git status` 确认干净）。
新增的是 schema、导出函数和测试；判定表本身保持原样，
它的字段集现在被测试**约束**而不是被修改。

## 5. 验证

- `test_blind_eval.py` 19 → **27 项**
- 离线套件 exit 0：**362 Python + 58 Node**
- 全程付费模型请求 0；既有运行记录与判定材料均未改动

**本记录不构成 E1/E2/E3 任何效果证据。** 它只说明：判定这一步产出的记录，
现在能通过仓库自己的 schema 校验了，而且 arm 不会因此泄漏进记录。
