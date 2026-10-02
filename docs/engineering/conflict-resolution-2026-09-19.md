# 协议 / schema / 计划冲突决议（2026-09-19）

对应压缩 WP1。只记录**当前有效规则**；旧文件保留原文，以本决议 + `AGENTS.md` + `docs/plan/v0.5-compressed-wp.md` 为准。

## 1 扩展开工

| 旧说法 | 新有效说法 |
|---|---|
| `AGENTS.md`：H1 未验证前禁止写扩展 / manifest / content script / service worker | WP1 材料与 harness 落到本分支后允许 MV3 扩展；H1 仍未验证，扩展≠效果 |
| v0.4 W10：E1 或自动 E2 有收益才进入扩展 | 工程可开工；收益判定仍独立，不得用安装包冒充增益 |
| v0.4 W8 报告：暂停 W10 | 被 2026-09-19 压缩计划覆盖为「做可加载试验扩展」 |

## 2 种子 stars 下限

| 旧说法 | 新有效说法 |
|---|---|
| `schemas/seed-set.schema.json`：`stars.minimum = 50` | `stars.minimum = 0`；热度不作排除条件 |
| `seed-tasks.draft.yaml` 冻结条件写 `stars (>= 50)` | 删除该门槛；须包含低热度材料 |
| E1 协议：不以 stars 下限排除冷门 | 维持；schema 向协议看齐 |

## 3 记录字段节号

| 旧说法 | 新有效说法 |
|---|---|
| `AGENTS.md` 曾写「protocol.md 第 7 节」为字段表 | 字段表是 **第 5 节**；第 7 节是继续/缩小/暂停 |
| `github_search.py` 注释「protocol 7」指 matched_fields | 改为第 5 节 |
| `seed-set.schema.json` 写「第 3 节种子字段」 | 已知目标诊断在协议 **第 2 节**；方法组才是第 3 节 |

## 4 冻结

| 旧说法 | 新有效说法 |
|---|---|
| 材料写好即可填冻结 SHA | 只能回填**已存在**提交 SHA；本分支材料落地后另一次提交才可回填 |
| HelloGitHub 为 schema 必填 | 可选线索之一，不得当唯一来源 |

## 5 评估题 vs 开发题

维持：`queries.yaml` 的 `dev` 与 `eval.batch_1` 分离；评估不得从开发题改写。种子诊断另存 `verified-seeds.jsonl`。

## 6 E3 冒烟 vs 真实片段

| 集合 | 用途 |
|---|---|
| `fragments-2026-09-17.md` | 仅冒烟：核对 excerpt＋label 管道 |
| `fragments-real-2026-09-19.md` | 真实公开项目 README/评论/限制/issue 摘录；对照仍未运行 |

## 7 许可证

决策 0003 仍开放。允许 `docs/decisions/0003-license-draft-proposal.md`。禁止添加已决定的根目录 `LICENSE`。
