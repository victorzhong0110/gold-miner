# 2026-10-05：A/B/C/M 运行无法产出 latency_cost.jsonl

把仓库里 4 个已记录运行逐个按 schema 校验时发现：`latency-cost.schema.json`
存在，但**只有 D 组写了对应的 `latency_cost.jsonl`**。A/B/C/M 三个都没有。
根因不是忘了写文件，而是**需要的那个数据从来没被测量过**。

## 1. 先说校验结果：没有 schema 违规

用 `jsonschema` 逐行校验「有 schema 且文件存在」的记录：

| 运行 | 文件 | 行数 | 结果 |
|---|---|---|---|
| 2026-09-22-w4-first | candidates / judgments | 100 / 45 | 全部合法 |
| 2026-09-28-readme-pair | candidates | 783 | 合法（judgments 为空） |
| 2026-10-04-bcm-minimax | candidates | 732 | 合法（judgments 为空） |
| 2026-10-04-d-minimax | candidates / judgments / latency_cost / failures | 169 / 0 / 25 / 8 | 全部合法 |

**共 1862 行，0 违规。** 记录形状本身是健康的。

## 2. 缺的是什么

| 运行 | `latency_cost.jsonl` | `failures.jsonl` |
|---|---|---|
| 2026-09-22-w4-first | 无 | 无 |
| 2026-09-28-readme-pair | 无 | 无 |
| 2026-10-04-bcm-minimax | 无 | 无 |
| **2026-10-04-d-minimax** | **有（25 行，合法）** | **有（8 行，合法）** |

`failures.jsonl` 已在同日由本会话另一条提交补上（工具侧）。
本条处理 `latency_cost.jsonl`，性质不同——见下。

## 3. 根因：耗时从来没被测量

`latency-cost.schema.json` 要求：

```
run_id, task_id, arm, elapsed_ms(整数≥0), github_requests, model_requests, visible_cost
```

而 `e1_pipeline.py` 在写文件之前**只有两个时间戳**：

```python
result['started_at'], result['finished_at'] = started_at, _utcnow()   # 整个 run 一次
```

**全文件没有 `time.monotonic()`。** 每个 (task, arm) 格子的两半都没计时：

- 模型生成（`generate(...)`）——没计
- GitHub 检索（`run_batch` 内的每题）——没计

所以 `elapsed_ms` 这个字段**没有数据来源**。这不是「忘了写文件」，
而是「要写的那个数从来没被采集」。直接照 schema 造一个文件只能填 0，
那比不写更糟——它会让人以为「耗时为 0」。

## 4. 为什么这个缺口重要

协议第 6 节的六项「观察项」之一就是：

> **成本与等待** | 实际请求、耗时、失败、人工投入和可见费用

而 WP4-07 长期停在 `partial`，理由正是「真实模型成本/等待仍未知」。
本次 `2026-10-04-bcm-minimax` 是目前唯一一次完整 A/B/C/M 实跑，
它的 `model_usage` 里有 token 计数（B 输入 8330 / 输出 1989 等），
但**没有逐题耗时**——所以「等待」这一半在任何记录里都不存在。

## 5. 修法：先测量，再写文件

1. `e1_batch.run_batch`：在每题开头取 `time.monotonic()`，在
   **正常路径、`except` 异常路径、取消路径**三处都写回
   `task_results[*]["elapsed_ms"]`（取消路径为 0，因为没干活）
2. `e1_pipeline.run_pipeline`：对每次 `generate(...)` 计时，按
   `(task_id, arm)` 累积
3. 新增 `latency_cost_rows(...)`：每 (task, arm) 一行，
   `elapsed_ms` = 检索耗时 + 生成耗时；`github_requests` 取已有的
   `attempted_requests`；`model_requests` 复用 `summarize_usage` 已有的
   `request_parameters` 判据；`main()` 写出 `latency_cost.jsonl`（空也写）

**`visible_cost` 一律不编造**：live 写 `unknown`，fixture 写
`fixture-no-model-calls`。真实费用是本工具无法知道的东西，
schema 只要求字符串，所以如实标注即可——这与 `model_cost: "unknown"` 一致。

## 6. 没有回填历史运行

**没有**给三个旧运行补 `latency_cost.jsonl`。它们的耗时从未被测量，
补一个全是 0 的文件等于宣称「当时耗时为零」。已用
`git status` 确认 `runs/` 目录零改动。

从已记录的 `pipeline.json` 可以**导出形状**（只读）：80 行
（20 题 × 4 臂），全部通过 schema 校验，但 `elapsed_ms` 全为 0——
这恰好说明为什么不能回填。

## 7. 验证

- `test_e1_pipeline.py` 17 → **24 项**，新增 7 项：
  三条路径都带 `elapsed_ms`、每 (task, arm) 一行、schema 校验、
  `visible_cost` 绝不编造、模型请求判据与 `summarize_usage` 一致、
  生成耗时计入格子、文件必写
- 其中一项用**会真的 sleep 的 stub** 断言 `elapsed_ms > 0`，
  证明测的是真实经过时间而不是占位 0
- 实跑一次 fixture：`latency_cost.jsonl` 40 行、schema 全合法、
  四臂齐全（fixture 模式无网络，故计数为 0，属如实）
- `python3 scripts/run_offline_suite.py` exit 0：**354 Python + 58 Node**
- 全程付费模型请求 0

**本记录不构成 E1/E2/E3 任何效果证据**，也不改变已完成运行的任何结论。
它只说明：下一次 A/B/C/M 运行起，「耗时」会第一次被记录下来。
