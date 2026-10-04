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
- [x] `concrete_model_id` 为 MiniMax-M3（2026-10-04 发起人决定，见 docs/decisions/0004-minimax-d-group.md）。B/C/M 实跑仍未运行。

## SHA 回填（只能填已存在提交）

在本分支**合并材料的提交出现之后**，另开提交填写，禁止在同一文件里写「将等于本提交」：

- [ ] `queries.yaml` `preregistration.*_frozen_commit`
- [ ] `run-settings.json` `freeze.*`

在未回填前保持 `null` / `unfrozen-no-run`。

## 运行后

- 不改本批材料。修复另开 `eval.batch_2`。
- 没有 `runs/<日期>-<标签>/` 就写「未运行」。
