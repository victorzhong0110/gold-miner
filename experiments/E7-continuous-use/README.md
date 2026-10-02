# E7 一周轻量日记

实际会话未运行。请为自愿参与者使用 P01 等代号，原始记录留在本地，不记录姓名、
邮箱、私有仓库、API key 或私人备注。每个发生观察的日期自行记录 JSONL；
没有机会用也如实记录，未回访不能填成「没有价值」。

每行字段：participant、date（实际 YYYY-MM-DD）、reading_lang（zh/en）、
action（seen/saved/tried/learned/revisited/no-opportunity/not-used）、repo
（规范 owner/repo；无项目可填 null）、reason（参与者实际解释）、minutes
（实际分钟，不知道填 null）、visible_cost（实际可见费用说明，不知道填 null）。

```sh
python3 scripts/stage_records.py diary /path/to/your-local-diary.jsonl
```

工具检查未来日期、重复记录、字段和意外凭据，汇总实际记录日期与动作。
seven_day_coverage 只表示至少七个真实日期覆盖七天，不是七日留存率，也不能证明效果。
最终必须回访本人，区分收藏、实际使用、学习、再访问和不用的原因。
没有记录不生成空白「已运行」结果。脚本测试的日记全部是 fixture。
