# E1 盲判表模板

用法：把各组前 5 候选合并去重后，**去掉 arm 名**再发给判定人。判定完成前回填组别。

状态：模板。尚无判定行（未运行）。

| blind_id | task_id | repo | purpose_fit | hard_conditions | kind | novel_to_judge | worth_following | reason | judge | judged_at | hidden_arm_to_fill_later |
|---|---|---|---|---|---|---|---|---|---|---|---|
| b-001 |  | owner/repo | yes/partial/no | satisfied/conflict/unknown | tool/library/tutorial/list/mirror/other | yes/no | yes/no/unknown | 原话或标记为技术判断 |  |  | （判定后填 A/B/C/M/D） |

规则：

- 未知不能算满足。
- 同一人构题+判定必须披露，不得写「盲测完成」。
- 本表空行不是数据。
