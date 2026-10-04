# 2026-10-05：判定分析漏了协议要求的 B→C，且「完整」标签曾经过宽

盲判材料即将由发起人判定，`blind_eval.py analyze` 是判定后立刻要跑的那一步。
本轮核对了它产出的比较项与协议第 6 节要求的比较项，发现对不上。

## 1. 协议要求三个比较，分析只产出两个

协议第 6 节原文：

> A→C 衡量整体辅助效果；**M→C 才更接近相同预算下的语言扩展贡献。B→C 判断复杂程度是否值得。**

| 协议要求 | 修前 `analyze` |
|---|---|
| A→C | ✅ `c_minus_a` |
| M→C | ✅ `c_minus_m` |
| **B→C** | ❌ **不存在** |

B→C 正是回答「跨语言扩展这套复杂度值不值得」的比较——也就是这个产品最核心的
决策问题。判定人跑完分析会拿不到这个数，只能自己手算，或者干脆不比较。

B 的 `suitable` 集合其实**已经算好了**（`groups['<task>:B']`），只是没有参与差集。

## 2. 「完整」这个标签曾经过宽

修前只有一个总开关：

```python
task_groups = {arm: groups.get(task + ':' + arm) for arm in ('A', 'C', 'M')}
complete = all(... for arm, g in task_groups.items())
```

**判定门只看 A、C、M，完全不看 B。** 后果：一个任务的 B 组判定**全部缺失**，
A→C 和 M→C 照样标成 `complete`——看起来结论完整，实际上协议要求的 B→C 那一半
根本无法回答。`complete` 这个词给出了它没有兑现的保证。

而 B 组判定本来就是逐 blind_id 校验过的（`analyze` 顶部逐行验证 `blind_id`
存在且不重复、四个字段取值合法、`reason`/`judge`/`judged_at` 非空），
所以 B 的数据一直是被收集的，只是差集没算、门也没看。

## 3. 修法：每个比较项各自带完整性

不再共用一个总开关：

| 比较项 | 需要 |
|---|---|
| `c_minus_a` | A 与 C 都判定完整且运行状态为 ok |
| `c_minus_m` | M 与 C 都完整 |
| `c_minus_b` | B 与 C 都完整 |

不完整时写 `{'status': 'incomplete-no-comparison', 'needs': [other, 'C']}`，
**绝不写空列表**——空列表会被读成「这组没有独有合适候选」，那是一个结论。
（这条延续了原有测试 `test_missing_judgments_do_not_become_zero_effect` 的意图，
只是现在逐项检查。）

这样 B 的缺失**只影响 B→C**，不会连累 A→C 和 M→C——它们各自仍然成立。

**D 组刻意不做差集。** D 走的是联网助手、请求预算也不同（模型请求 23 次 vs
60 次），协议第 6–7 节明确 D 是「代表任务子集试用，不与全量平均混用」。
算一个 D−C 差集会看起来像同条件对比，而它不是。D 的逐任务 `suitable` 仍在
`groups['<task>:D']` 里可见，留给人读；输出另加 `d_not_differenced` 说明原因。

每项差异都带 `protocol_basis: 'E1 protocol section 6'`，让映射可核对，
而不是藏在代码里。

## 4. 拿已记录运行核对：两次失败会吃掉比较项

用 `2026-10-04-bcm-minimax` 的**真实** per-arm 任务状态跑一遍结构检查
（判定内容是**模拟**的，只为看哪些比较在结构上可得，**不是结果**）：

| 任务 | c_minus_a | c_minus_m | c_minus_b |
|---|---|---|---|
| `zh2en-eval-01` | 可比 | 可比 | 可比 |
| `zh2en-eval-10`（B partial，GitHub 422） | 可比 | 可比 | **不可比** |
| `en2zh-eval-03`（C blocked，模型 JSON 解析失败） | **不可比** | **不可比** | **不可比** |

**20 题里 13 题至少有一项比较不可得。** 根因就是那两次失败：
B 的 partial 让该题失去 B→C；C 的 blocked 让该题三项全失。

修前的代码会在 `zh2en-eval-10` 上把 A→C、M→C 标成 complete——
那是个过宽的保证。修后如实分开。

**这意味着发起人判定前应当知道**：这批材料最多只能在约 7 题上给出完整的三项比较。
是否值得按这个规模判定、或先处理那两题，属发起人决定。

## 5. 验证

- `test_blind_eval.py` 15 → **19 项**，新增 4 项覆盖：
  三项比较都产出、B 缺失只废 B→C 不牵连 A→C/M→C、只缺 B 判定时同理、
  D 永不做差集但其集合仍可见
- 原有 `test_missing_judgments_do_not_become_zero_effect` 改为逐项断言
  （形状变了，意图更强：以前只查一项，现在三项都查，且断言不是 list）
- `python3 scripts/run_offline_suite.py` exit 0：**347 Python + 58 Node**
- 全程付费请求 0；判定材料与既有运行记录均未改动

**本记录不构成 E1/E2/E3 任何效果证据。** 第四节表格里的「可比/不可比」是
结构判断，不是效果结论；`product_effect` 仍为 `not-concluded`。
