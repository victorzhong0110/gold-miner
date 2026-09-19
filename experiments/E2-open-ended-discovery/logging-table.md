# E2 会话日志表

一行一个会话。机器可读副本用 JSONL，字段与 `schemas/e2-session.schema.json` 一致。

| session_id | pair | order | condition | participant | reading_lang | start | end | start_url | interests | opened_repos | worth_follow | reason_quote | abandon_reason | prep_minutes | github_requests | model_requests | visible_cost | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e2a-p1-a | P1 | A_then_B | A | owner-blocked | zh | 未运行 | 未运行 |  |  |  |  |  |  | 未知 | 未知 | 0 | 未知 | 未运行 |
| e2a-p1-b | P1 | A_then_B | B | owner-blocked | zh | 未运行 | 未运行 |  |  |  |  |  |  | 未知 | 未知 | 0 | 未知 | 未运行 |
| e2a-p2-b | P2 | B_then_A | B | owner-blocked | zh | 未运行 | 未运行 |  |  |  |  |  |  | 未知 | 未知 | 0 | 未知 | 未运行 |
| e2a-p2-a | P2 | B_then_A | A | owner-blocked | zh | 未运行 | 未运行 |  |  |  |  |  |  | 未知 | 未知 | 0 | 未知 | 未运行 |

禁止模型代填未发生的用户原话。
