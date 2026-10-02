# E2 会话日志表（未运行）

完整机器记录见 [recording.md](recording.md)。会话和候选分别用 JSONL；
实际会话 status=recorded 时须有完整字段与明确的未知项，不能使用下面的规划行充当结果。

| session_id | pair | order（既有计划） | condition | participant | reading_lang | status |
|---|---|---|---|---|---|---|
| e2a-p1-a | P1 | A_then_B | A | owner-blocked | zh | 未运行 |
| e2a-p1-b | P1 | A_then_B | B | owner-blocked | zh | 未运行 |
| e2a-p2-b | P2 | B_then_A | B | owner-blocked | zh | 未运行 |
| e2a-p2-a | P2 | B_then_A | A | owner-blocked | zh | 未运行 |

翻译条件、实际起止时间、请求次数/成本和用户原话尚未观察，不能先填写。
模型不得代填未发生的用户原话；正式冻结与是否执行仍由发起人决定。
