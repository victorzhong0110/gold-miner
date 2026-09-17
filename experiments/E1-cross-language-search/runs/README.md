# E1 runs 目录约定

每次运行一个目录：`runs/<日期>-<标签>/`，每个目录恰含 3 个文件：

- `candidates.jsonl`：字段见 `../schemas/candidates.schema.json`（依据 protocol.md 第 7 节），一行一条。
- `judgments.jsonl`：字段见 `../schemas/judgments.schema.json`（依据 protocol.md 第 7 节），一行一条。
- `report.md`：数据、指标、局限、按 protocol.md 第 9 节的判定，以及漏掉的好结果（依据 protocol.md 第 11 节）。

种子集另见 `../schemas/seed-set.schema.json`（依据 protocol.md 第 3 节），冻结后提交，不放在 runs 目录下。

没有真实运行就不要建日期目录。
