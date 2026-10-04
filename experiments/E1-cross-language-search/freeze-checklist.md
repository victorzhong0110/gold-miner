# E1 冻结检查清单

评估运行前逐项打勾。材料存在 ≠ 已冻结 ≠ 已运行。

## 分离

- [x] `queries.yaml` 的 `dev` 与 `eval.batch_1` 分开，id 不重叠
- [x] 种子诊断不在开放评估题里（`verified-seeds.jsonl`）
- [x] 冒烟 E3 与真实片段分开

## 种子

- [x] 8 条已知目标，两方向各 4
- [x] 多来源（API / README / W2），HelloGitHub 不是唯一来源（本批未用）
- [x] 含低热度：`LingDongWeb` 29、`File-Transmit-pc` 30
- [x] **无 stars 下限**
- [x] 每条有核对日期与方法
- [ ] 开放题作者书面确认未看种子答案（owner-blocked：未收到书面确认）

## 提示词与预算

- [x] B/C/M/D 提示词在 `prompts/`
- [x] `run-settings.json` 预算 A1 / B2 / C4 / M4
- [ ] `concrete_model_id` 仍为 null（owner-blocked：无发起人模型探测）

## SHA 回填（只能填已存在提交）

在本分支**合并材料的提交出现之后**，另开提交填写，禁止在同一文件里写「将等于本提交」：

- [ ] `queries.yaml` `preregistration.*_frozen_commit`
- [x] `run-settings.json` `freeze.*`（填于 `70af4ea`）—— **但指向的提交不成立，见下**

### ★ 2026-10-05：已填的 SHA 指向一个不包含全部材料的提交

`run-settings.json` 的四个指针都填了 `6010be0e…`（`Freeze W4 E1 materials without
starting retrieval`，2026-09-22）。核对结果：**这个提交里没有两份关键材料。**

| 材料 | 在 `6010be0e` | 说明 |
|---|---|---|
| `prompts/b-translate.txt` | 在 | 未变 |
| `prompts/c-rewrite.txt` | 在 | 未变 |
| `prompts/d-assistant.txt` | 在 | 未变 |
| `prompts/m-rewrite.txt` | **不在** | M 组提示词是冻结之后才加入的（`fafcb8d`） |
| `verified-seeds.jsonl` | **不在** | 该文件在冻结时还不存在，现有 8 行全部晚于冻结 |
| `prompts/d-control.template.jsonl` | **不在** | 2026-10-05 新增（D 组录入模板） |

也就是说：M 组是四个实验臂之一，它的提示词从未被冻结过；种子集同样。
现在若直接跑 E1，M 组结果会来自一个「未冻结的提示词」，而事后无法从记录里看出这一点——
这正是冻结机制要防的事。因此 `concrete_model_id` 虽然仍为 null（owner-blocked），
**冻结本身也不成立**，两者都要在正式运行前解决。

自动核对：`python3 scripts/e1_freeze_check.py`，机器可读结果见
[`freeze-status.json`](freeze-status.json)（当前 `status: "stale"`）。
`test_e1_freeze_check.py` 会在记录与真实材料不一致时失败，所以这个状态不会再静默腐烂。

**修复方式（属于发起人决定，本轮不代做）**：选定 `concrete_model_id` 后，
另开一个提交把四个指针重新指向**确实包含全部材料的提交**，并同步刷新
`freeze-status.json`。在 `status` 变为一致之前，不得把本批称为「已冻结」。

## 运行后

- 不改本批材料。修复另开 `eval.batch_2`。
- 没有 `runs/<日期>-<标签>/` 就写「未运行」。
