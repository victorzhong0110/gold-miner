# 2026-10-05：A/B/C/M 运行没有写 failures.jsonl

补上一条记录形状不一致的问题：E1 的 D 组运行会写 `failures.jsonl`，
A/B/C/M 运行不写，而 `schemas/failures.schema.json` 明确定义了这个文件。
结果同一个实验的两类记录形状不同，消费方必须为 A/B/C/M 特判。

## 1. 先说清楚：失败信息没有丢

这一点必须先澄清，否则容易把问题说过头。逐任务失败**已经在 `pipeline.json` 里**，
机器可读：

```
B  zh2en-eval-10  status=partial
   errors: [{"variant_index": 1, "api_query": "I need a tool that can automatically back up
             photos from my phone to my home computer, ...",
             "error": "HTTPError: HTTP Error 422: Unprocessable Entity"}]

C  en2zh-eval-03  status=blocked
   errors: []
   reason: "arm C coverage miss: task en2zh-eval-03 absent or empty in variants_by_task; ..."
```

所以**这不是「失败不可诊断」**（那是上一条报告里 B/C/M 模型原文的问题，已修）。
这里是：**该有的独立账本没写**，失败信息只存在于 `pipeline.json` 的嵌套结构里，
而 schema 规定的平铺记录没有生成。

## 2. 缺在哪

| 运行目录 | `failures.jsonl` |
|---|---|
| `2026-09-22-w4-first` | 无 |
| `2026-09-28-readme-pair` | 无 |
| `2026-10-04-bcm-minimax` | 无 |
| `2026-10-04-d-minimax` | **有** |

`schemas/failures.schema.json` 已存在，必填 `run_id`/`task_id`/`arm`/`code`，
可选 `message`，且 `additionalProperties: false`。
`e1_d_assistant.py` 多处写这个文件（`:1225`、`:1378`、`:1470`、`:1481`）。
而 `e1_pipeline.main()` 原本只写 `pipeline.json`、`generation.jsonl`、`candidates.jsonl`。

更别扭的是：`e1_pipeline.py:194-196` **已经检测到**失败并据此返回 exit 2
（`any(code != 'ok')` 或 `failed_requests` / `tasks_blocked`），
却只把结果交给退出码，不落盘。退出码没有细节，所以实际可读的信息比已经算出来的少。

## 3. 修法

新增 `e1_pipeline.failure_rows(result)`，在 `main()` 里写出 `failures.jsonl`：

- **不编造任何字段**。每一条都来自 `generation_records` 或 per-task 的
  `status` / `errors` / `reason`，这些本来就在 result 里
- 遵守 `additionalProperties: false`：一行只有 `run_id`、`task_id`、`arm`、
  `code`、`message` 五个字段。出问题的 `api_query` 留在 `pipeline.json`，
  不塞进账本
- **空也写文件**。缺文件和「跑过但没失败」无法区分；空文件才表达后者

从**已记录的** `2026-10-04-bcm-minimax` 派生（仅读取，不修改）得到 3 行，
两条真实失败都能还原：

```json
{"run_id":"2026-10-04-bcm-minimax","task_id":"en2zh-eval-03","arm":"C","code":"bad_response","message":"model output JSON parse failed"}
{"run_id":"2026-10-04-bcm-minimax","task_id":"zh2en-eval-10","arm":"B","code":"partial","message":"HTTPError: HTTP Error 422: Unprocessable Entity"}
{"run_id":"2026-10-04-bcm-minimax","task_id":"en2zh-eval-03","arm":"C","code":"blocked","message":"arm C coverage miss: ..."}
```

注意第 1、3 行是**同一个 `en2zh-eval-03`**：一次查询生成失败，任务因此被记为 blocked。
这是两个层次的事实，所以**行数不等于失败任务数**——统计时要去重 `task_id`。
这一点写进了函数 docstring 和报告，避免后来者按行数下结论。

## 4. 没有回填历史运行

**没有**给 `2026-10-04-bcm-minimax` 补一个 `failures.jsonl`。
那次运行没有产生这个文件；事后补一个会让它看起来像是当时跑出来的，
属于伪造记录。同理也没动三个更早的运行目录。

所以本条修复只对**后续**运行生效。历史运行的失败仍需从 `pipeline.json` 读，
这一点在 STATUS 里写明。

## 5. 顺带发现，但本轮不改：退出码与账本口径不一致

`e1_pipeline.py:194` 判定失败的条件是
`any(generation code != ok) or any(failed_requests or tasks_blocked)`。
它**不含** `tasks_partial`。也就是说：一次只有「部分完成」而
`failed_requests` 恰好为 0 的运行，会返回 exit 0 ——同时账本里却有 `partial` 行。

本次记录的运行没有触发（B 的 partial 伴随 `failed_requests: 1`），
但这是口径不一致。**是否让 partial 也算失败，属发起人决定**：
一边可以认为「部分完成必须非零退出」，另一边可以认为「部分完成是正常结果，
退出码只表示完全失败」。本轮不擅自改，只在此记录。

## 6. 验证

- `test_e1_pipeline.py` 10 → **17 项**（新增 7 项）：生成失败成行、partial 记错误、
  blocked 记 reason、ok 不入账本、一次原因两层两行、schema 校验（含 jsonschema
  缺失时的回退）、空也写文件
- `python3 scripts/run_offline_suite.py` exit 0：**343 Python + 58 Node**
- 全程付费请求 0；`e1_pipeline` 的查询规则与行为未变（仅新增输出文件）

**本记录不构成 E1/E2/E3 任何效果证据**，也不改变已完成运行的任何结论。
