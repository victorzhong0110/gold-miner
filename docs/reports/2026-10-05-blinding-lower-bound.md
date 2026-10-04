# 2026-10-05：盲判遮蔽的下界，以及为什么 salt 无效

发起人审查把 `strict_blinding` 标为 `not-established`。本轮把这件事做到底：
**证明这里的遮蔽有下界**，并修掉一个在任何威胁模型下都错的缺陷。

## 1. 结论先说

> **只要源运行记录可被判定人取用，按 `(task_id, repo)` 就能 100% 反推组别。
> 任何哈希、salt 或 ID 方案都改变不了这一点。**
> 本项目的遮蔽是**流程控制**（谁能看到哪些文件），不是密码学控制。

实测（只用公开记录，完全不用 `blind_id`）：

| 匹配依据 | 可归因行数 |
|---|---|
| 仅 A/B/C/M 的 `candidates.jsonl` | 140 / 233 |
| A/B/C/M + D 的 `candidates.jsonl` | **233 / 233** |
| 其中可确定**单一**组 | 196 / 233 |

D 组的记录补上后，**每一行都能定位到它的来源运行**。

**为什么会这样**：判定要判断「用途是否适合」，就必须知道**查询**和**仓库**——
而这两样恰好都是公开运行记录的可连接键。遮蔽掉 `blind_id` 不影响这一点，
因为行里还明文写着 `task_id` 和 `repo`。

## 2. 我之前的 salt 是一个无法生效的控制

我加 salt 时的结论是「196 → 0」。**那是错的。** 独立验证：

```
只用 (task_id, repo) 匹配、完全忽略 blind_id：
  233/233 行可匹配
  196 行可确定单组归属
```

与未加 salt **完全相同**。salt 只随机化 `blind_id` 这个值，而身份信息
本来就在公开文件里明文写着——所以它保护不了任何东西。

这不是实现问题，是**方案选错了**：我给一个「身份本就公开」的场景加了一个
只作用于 ID 的密码学装置。发起人审查已把 `audit_masking` 改为同时测两条路径
（重算 `blind_id` / 匹配公开身份），现在它会如实报告加盐后仍是 233/233。

## 3. 修掉的缺陷：映射表和判定表放在同一个目录

这是**在任何威胁模型下都错**的一处，与 salt 无关：

```
experiments/E1-cross-language-search/evaluation/2026-10-04-minimax/
  blind-candidates.jsonl
  blind-sheet.md
  blind-key.json      ← 毁掉遮蔽的那份文件，就在交给判定人的材料里
```

新增 `build_judge_bundle()` 与 `--judge-bundle`：判定人收到的目录**只含**

| 文件 | 内容 |
|---|---|
| `blind-candidates.jsonl` | 待判行 |
| `blind-sheet.md` | 判定表（可选，`--sheet` 传入） |
| `disclosure.json` | 机器可读的披露 |

**不含 `blind-key.json`**，也不含任何 repo→arm 映射。

## 4. 披露文件记录下界，而不是假装有解

`disclosure.json` 写的是实测事实，不是承诺：

```json
{
  "rows": 233,
  "key_included": false,
  "rows_joinable_to_public_source_runs": 233,
  "attribution": "total",
  "strict_blinding": "not-established",
  "salt_effect": "randomizes blind_id only; it does not hide task_id/repo, so it does not change attribution",
  "why": "判定必须知道查询与仓库才能判断，而两者都是公开运行记录的可连接键……",
  "judge_must_be_disclosed": "判定前须披露：是否看过源运行记录、映射表或本仓库。若由未接触源记录的独立判定人执行，本材料按来源遮蔽有效；否则须在 notes 中写明已见信息。"
}
```

`rows_joinable_to_public_source_runs` 是**当场算出来的**，不是写死的文案；
判定人拿到材料时就知道这批东西能被反推到什么程度，而不是被告知「已遮蔽」。

## 5. 什么才算真遮蔽（本项目的可选项，属发起人决定）

技术手段已到下界，剩下的都是流程选择：

1. **独立判定人**：把 bundle 交给一个没有本仓库访问权的人。
   此时源记录不可达，来源遮蔽在实践中成立。协议要求披露判定人身份，本就指向这个方向。
2. **延后公开**：判定完成前把源运行记录（`runs/*/candidates.jsonl`、`blind-key.json`）
   移出仓库或设为不可见，判完再放回。
3. **接受来源遮蔽 + 如实披露**：按现状判定，结论写成
   「带已知可还原组别属性的来源遮蔽判定」，并披露判定人看过什么。

三条都可辩护，取决于要不要为「判定人不是我」付出成本。**本轮不代做选择**，
只把 bundle 与披露准备好，并把「加盐就能遮蔽」这个错误说法从文档里清掉。

## 6. 验证

- `test_blind_eval.py` 30 → **35 项**，新增 5 项：
  bundle 不含 key、bundle 无 repo→arm 映射、披露报告实测下界（233/233、total、
  `not-established`）、**加盐后仍不得声称严格遮蔽**、披露要求写明判定人见过什么
- 逐项断言披露字段是**重算得到**的：改材料或改源记录都会让测试失败
- 实跑 `--judge-bundle`：产出 3 个文件，`blind-key.json` 不存在，
  正则扫描无 `"arm":` / `"links":`
- 离线套件 exit 0：**376 Python + 58 Node**
- 全程付费模型请求 0、GitHub 搜索请求 0；未改任何已记录产物或冻结材料

**本记录不构成 E1 任何效果证据。** 真人判定仍未发生（0 条判断），
`product_effect` 仍为 `not-concluded`。
