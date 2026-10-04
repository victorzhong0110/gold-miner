# 2026-10-05：schema 一致性扫描的收口记录

本记录用于**结案**：把「按 schema 校验已记录产物」这套做法从 E1 扩到
E2/E3/E5/E6/E8 之后，逐目录的结论是什么，含**一个我自己产生的假发现**。

目的是让下一个人不必重跑这套扫描，也不必重蹈那个假发现。

## 1. 结论一览

| 目录 | 有 schema？ | 有产物？ | 结论 |
|---|---|---|---|
| E1 | 9 个 | 有 | 本会话已修 4 处（failures / latency_cost / judgments-blind / B→C） |
| **E6** | 1 个 | 有 | **发现真实缺陷：schema 不可满足。已修**（见 [同目录报告](2026-10-05-e6-schema-unsatisfiable.md)） |
| E3 | 1 个（`observation`） | 5 个 | **一个假发现，已排除**（见第 2 节） |
| E2 | 2 个 | 无 | 无产物。会话未发生（WP2-05 `pending-human`），符合预期 |
| E5 | 无 | 1 个 | 无 schema，但有消费者 `scripts/test_stage_records.py` 自带检查 |
| E8 | 无 | 2 个 | 无 schema，但有消费者 `e8_materials.py` 自带检查 |

**全仓库 13 个 schema 现已全部可满足**（`required - properties` 为空，
或 `additionalProperties` 非 `false`）。

## 2. E3 的假发现：被我自己否掉

### 机械扫描的输出

`experiments/E3-faithful-reading/observations-2026-09-21.jsonl` 的每一行都
**不满足** `schemas/observation.schema.json`：它有 `frag` 而 schema 要 `frag_id`，
并缺 `source_text` / `source_url` / `categories` / `must_keep` / `elapsed_ms` /
`error_class` / `terminology_kept` / `changes_understanding` / `error_location` /
`judge` / `judged_at` 共 11 个必填字段。

单看这一条，完全可以写成「E3 观察记录不符合自己的 schema」。

### 为什么这是错的

`test_observations.py` 的文档字符串把它的性质写得很清楚：

> 本测试只断言**「骨架完整且诚实为空」**：8 行、`frag` 与语言对正确、
> 判定列全为 `未运行`、未知列全为未知、无译文内容、无密钥模式。
> **未来真实对照运行时，须另起新日期 JSONL，不得直接改本文件的值。**

所以：

- 它是**有意准备的空骨架**，不是一次完成的观察。`frag` 是刻意的字段名
- 它的判定列全是 `未运行`——**没有任何东西被运行过**，所以没有 `judge`/`judged_at`
  正是诚实的表现，而不是缺漏
- schema 是为**已完成的观察**设计的（要求 `judge`、`judged_at`、`source_url`），
  拿它去校验一份「尚未运行」的模板，本身就是错配
- 真正的对照运行是 `runs/2026-09-22-w6/observations.jsonl`，它**通过**该 schema

**结论：不是缺陷，是扫描方法的假阳性。** 若按机械结果动手「修」，会去给一份
刻意留空的模板补上伪造的 `judge` / `judged_at`——那正好违反本仓库
「不得伪造实验结果、未运行就写未运行」的纪律。

## 3. 可复用的判别方法

机械比对「每个 JSONL × 每个 schema」很容易出这种假阳性。判别式：

> **这个文件是「已完成的记录」，还是「文档化的空模板」？**
>
> 1. 有没有消费者在读它？
> 2. 消费者的文档字符串/断言有没有说明它**按设计就是空的**？
> 3. 它的时间戳是否早于同一实验第一次真实运行？
>
> 三条都指向「模板」→ **不改**，只记录。
> 指向「已完成记录却不合 schema」→ 才是缺陷（E6 就是这种）。

E5 / E8 的情形是第三种：没有 schema，但有消费者自带检查，
所以**不存在被破坏的契约**，只是没写 schema——那是文档缺口，不是缺陷，本轮不动。

## 4. 边界

- 本记录只说明「记录契约是否自洽」，**不涉及任何实验是否有效**
- E1/E6 的探测与评估本身状态不变：E6 仍是「未运行」，
  E1 真人盲判仍未发生
- 本轮未改任何已记录产物、未改任何提示词或冻结材料
- 离线套件 exit 0：362 Python + 58 Node
