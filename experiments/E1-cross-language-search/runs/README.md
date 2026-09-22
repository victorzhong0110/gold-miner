# E1 runs 目录约定

每次运行一个目录：`runs/<日期>-<标签>/`。真实运行后目录包含这 4 个文件：

- `candidates.jsonl`：字段见 `../schemas/candidates.schema.json`（依据 protocol.md 第 5 节记录格式；判定窗口见第 4 节），一行一条。
- `judgments.jsonl`：字段见 `../schemas/judgments.schema.json`（依据 protocol.md 第 5 节记录格式；判定窗口见第 4 节），一行一条。
- `report.md`：数据、指标、局限、按 protocol.md 第 7 节对照后仍不能下的结论，以及漏掉的好结果；交付物要求见第 9 节（协议共 0–9 节，无第 11 节）。第 7 节的继续、缩小或暂停不在证据不足时写成已决定。
- `manifest.json`：协议第 5 节的运行级字段（run_id、batch、materials_commit、预算、实际请求、错误、起止时间、模型请求数）。候选行里没有这些字段。

种子集另见 `../schemas/seed-set.schema.json`（依据 protocol.md 第 2 节），冻结后提交，不放在 runs 目录下。

没有真实运行就不要建日期目录。
