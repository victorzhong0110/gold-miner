# 2026-10-05：提示词与 pipeline 查询规则互相矛盾（潜在失败，未触发）

复核 `runs/2026-10-04-bcm-minimax/report.md` 的「不能下的结论」时，发现一条已被
记录但一直没处理的矛盾：**C 组提示词明确许可的搜索语法，正是 pipeline 会抛
`ValueError` 拒绝的语法。** 本次未触发，所以没有影响已完成运行；但下一次 C 组
运行可能因它失败，而且失败会被记成模型错误。

## 1. 矛盾在哪

| 位置 | 内容 |
|---|---|
| `prompts/c-rewrite.txt:13` | 「需要限定字段时**只用 in:description**；**stars 可用**但不是必须」 |
| `scripts/e1_pipeline.py:31-32` | 命中 `language:\|in:\|stars:\|repo:\|user:\|org:` 或 `owner/repo` 即 `raise ValueError('main comparison cannot inject field, star or repo filters')` |

也就是说：提示词叫模型用 `in:description` 和 `stars`，pipeline 随后就把它拒掉。
模型**照提示词做**才是错的，失败却会记在模型头上。

三组提示词里只有 C 是这样：

| 组 | 规则行 | 对被拒限定符的态度 |
|---|---|---|
| B | `b-translate.txt:14` | 「不准加**任何** GitHub 搜索语法（如 in:readme、in:description、stars、language: 等）」——**全面禁止** |
| C | `c-rewrite.txt:13` | 禁 `in:readme`、禁 `language:`（`:14`），但**许可** `in:description` 与 `stars` |
| M | `m-rewrite.txt:14` | 「不准加 in:readme、language:、stars: 等」——**只列三个**，`in:description`/`repo:`/`user:`/`org:` 完全未提 |

M 属于另一种问题：不是许可，而是**没告诉模型不许用**。模型若无意写出
`in:description`，同样会被 pipeline 拒绝并记为失败。

## 2. 为什么 pipeline 的规则是对的

主比较的基线 A 是**无限定符的默认搜索**。若 B/C/M 任一组能用字段或 stars 限定，
各组搜索空间就不同，`C−A`、`C−M` 这类集合差就不再衡量跨语言改写，
而混入了「谁用了更好的检索过滤」。

所以要改的是提示词，不是 pipeline。这也和 AGENTS.md 第 23 条一致：
不设 stars 下限，热度只作辅助排序信号——用 `stars:` 去缩窄查询与这个方向相反。

## 3. 本轮不修，为什么

prompts 是**冻结材料**，protocol 运行后条款写明「不改本批材料。修复另开
`eval.batch_2`」。`2026-10-04-bcm-minimax` 记录的
`prompt_sha256_16 = 9c6d37741f4e21fb` 指向当前这份 C 提示词；改它会破坏该记录的可复现性。

修法归属发起人（材料属主）。本轮做的是**让矛盾无法被忽略**。

## 4. 一个必须记录的教训：我第一版检查器造了假发现

最初的 `e1_materials_check.py` 试图从中文散文里判断某个限定符是「允许」还是「禁止」。
它给出的结论是错的：

- 把 C 的「本步**不要写** in:readme」判成**允许**
- 把 M 的「**不准**加 …stars:」判成**允许**

如果照单全收，就会去「修」两个根本不存在的问题——正是本机反复出现过的
「简单冒烟就认为是 bug 但实际不是」。所以**推翻重写**：

新版**只报告机械可验证的事实**：

- 某个被 pipeline 拒绝的限定符，提示词**有没有提到**（存在性，不是意图）
- 因此提示词**从未告诉模型不许用**的有哪些
- 承载禁止条款的行号与原文（可引用核对）

它不再输出任何「允许/禁止」判断。

**意图级判断改由人工记录 + 引用 + 棘轮测试**：`materials-status.json` 里
每条 `recorded_divergences` 都带 `file:line` 与原文 `quote`，
`test_e1_materials_check.py` 断言**该行至今仍含该原文**。
一旦提示词被修正，测试立刻失败，逼着更新记录——
所以这条声明不可能烂成一句关于仓库的假话。

## 5. 验证

棘轮双向验证（临时改动再还原）：

| 状态 | 结果 |
|---|---|
| 现状（C 许可 in:description/stars） | 10/10 通过 |
| 临时把 C 改成「不准加任何 GitHub 搜索语法」 | **2 项失败**：`recorded_divergences_still_exist_at_their_citations`、`recorded_status_matches_the_recomputed_coverage` |
| 还原 | 10/10 通过 |

检查规则本身也从 pipeline 读（`e1_pipeline.forbidden_query_syntax`），
不在检查器里复刻一份，避免两处漂移。

`python3 scripts/run_offline_suite.py` exit 0：**336 Python + 58 Node**，
全程付费请求 0。

## 6. 给下一批次的具体动作

1. `c-rewrite`（下一批次版本）删去 `in:description` 与 `stars` 的许可，改为全面禁止
2. `m-rewrite` 补齐 `in:description`、`in:name`、`repo:`、`user:`、`org:`
3. 重跑 `python3 scripts/e1_materials_check.py`，应翻转为
   `all_qualifiers_covered: true`；同时更新 `materials-status.json` 的
   `resolution.status`
4. B 组已有「任何…等」全面禁止，无需改

**本记录不构成 E1/E2/E3 任何效果证据。** 已完成的 `2026-10-04-bcm-minimax`
与 `2026-10-04-d-minimax` 未触发该矛盾，两份记录的结论不因此改变。
