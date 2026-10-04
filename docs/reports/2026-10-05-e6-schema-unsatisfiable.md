# 2026-10-05：E6 的 probe-record schema 不可满足，任何记录都通不过

把「按 schema 校验已记录产物」这套做法从 E1 扩到 E2/E3/E6 时，在 E6 找到一个
**比前两次更严重**的问题：不是工具少产字段，而是 **schema 本身自相矛盾**。

## 1. 缺陷

`experiments/E6-api-probe/schemas/probe-record.schema.json`：

| | 数量 |
|---|---|
| `required` 里的字段名 | **30** |
| `properties` 里描述的字段 | **16** |
| 既 required 又不在 properties 里 | **14** |
| `additionalProperties` | `false` |

那 14 个字段是：`run_id`、`started_at`、`finished_at`、`base_url`、`model`、
`protocol`、`max_output_tokens`、`cancelled_before_send`、`cache_hits`、
`visible_response_id`、`response_format`、`error_detail`、`billing_note`、`prompt`。

于是：**schema 要求这 14 个字段，同时 `additionalProperties: false` 又禁止它们存在。**
构造一个只带 30 个必填键的对象，仍报 16 个 `additionalProperties` 错误。

> **这个 schema 无法被任何对象满足。** 不是「记录不合规」，是「没有任何记录能合规」。

## 2. 为什么一直没被发现

`test_e6_probe.py` 里有一处看起来正好在管这件事：

```python
self.assertEqual(set(record), set(schema["required"]))
```

它断言**工具产出的字段名集合等于 schema 的 required 集合**——意图完全正确，
而且这个断言一直是通过的（工具确实产出 30 个字段，required 确实是 30 个）。

但它**只比对了名字，没有拿 schema 去过一遍记录**。
名字对上了，schema 能不能接受这份记录，没人在意。
差一步就能抓到这个 bug。

## 3. 方向判断：是 schema 错，不是工具错

我先确认是哪一边有问题，再动手：

| 比较 | 结果 |
|---|---|
| 工具产出字段 | 30 |
| schema `required` | 30 |
| **schema 缺描述的必填字段** | **0**（工具没有任何 required 缺项） |
| schema 允许的字段 | 16 |

**工具产出的是严格的超集**：30 个必填一个不缺，另外还带了 14 个
schema 忘了声明的字段——而这 14 个都是合理的探测事实
（`base_url`、`model`、`prompt`、`started_at`/`finished_at`、`visible_response_id`、
`cache_hits`、`billing_note`、`cancelled_before_send`、`error_detail`、
`max_output_tokens`、`response_format`、`protocol`、`run_id`）。

所以该改 schema，不是削工具的字段。

## 4. 修法

### 4.1 补齐 14 个字段声明

在 `properties` 中补上这 14 个字段，类型取自**实测**（今日新生成的记录与
2026-09-22 的已记录记录，两者形状一致）：

- `run_id`/`started_at`/`finished_at`/`base_url`/`model`/`protocol`/`prompt`/
  `billing_note`/`response_format`/`visible_response_id`/`error_detail` → 字符串
  （未配置时如实写 `未知`，与该实验既有约定一致）
- `cancelled_before_send` → boolean
- `cache_hits`/`max_output_tokens` → integer ≥ 0

并给 `run_id` 补了 `minLength: 1` 与说明——它本来就在 `required` 里，
却连描述都没有，而仓库里另外 12 个 schema 都要求 `run_id`。

### 4.2 让测试真的过一次 schema

`test_e6_probe.py` 新增两个模块级断言：

- `assert_schema_is_satisfiable(schema)`：`required - properties` 必须为空。
  这条直接对应本次缺陷，且不需要 `jsonschema` 也能跑
- `assert_record_validates(record, schema)`：用 `jsonschema` 真验一遍；
  缺 `jsonschema` 时回退到「必填齐全 + 无 schema 禁止的多余字段」

原有的名字比对**保留**——它是有价值的，只是原来单独用不够。

## 5. 验证

| 检查 | 结果 |
|---|---|
| 补声明前的今日新记录 | **INVALID**（`additionalProperties`） |
| 补声明后的今日新记录 | **VALID** |
| **2026-09-22 的已记录记录** | **VALID** |
| 只带 30 个必填键的最小对象 | `additionalProperties` 错误 0 → schema 可满足 |
| 重新引入原缺陷（删掉 14 个声明） | 测试**失败** |
| 还原 | 14/14 通过 |
| 全仓库 13 个 schema 的可满足性 | **全部可满足**（E6 是唯一破损的） |

**2026-09-22 那条已记录记录现在也通过了**——这本身就是「schema 错、工具没错、
产物没错」的最强佐证：那份产物从头到尾都是对的。

## 6. 顺带的全仓库扫描

把可满足性检查推广到全仓库 13 个 schema：

```
candidates / failures / hits / judgments / judgments-blind / latency-cost
queries / rank / seed-set / e2-candidate / e2-session / observation / probe-record
```

除 E6 外全部可满足。E3 的 `observation.schema.json` 有 9 个 required 未描述，
但它 `additionalProperties: true`，因此**不构成破损**（只是文档不全），
本轮不动。

## 7. 验证与边界

- 离线套件 exit 0：**362 Python + 58 Node**（未新增测试方法，只加强了既有断言）
- 全程付费请求 0；`e6_probe.py` 行为**未改**，只改 schema 与测试
- 未改任何已记录产物

**本记录不构成 E6 任何效果证据。** E6 探测本身仍是「未运行」，
本轮只修好了它的记录契约。

## 8. 可复用教训

> 断言「工具产出的字段名 == schema 的 required 集合」**不等于**「记录能通过 schema」。
> 前者是名字比对，后者才是契约。差一步，schema 就可以同时
> 「要求」和「禁止」同一批字段而长期无人察觉。
>
> 更一般的：`required - properties` 非空且 `additionalProperties: false`
> ⇒ schema 不可满足。这是一条三行就能查完、不需要任何领域知识的检查。
