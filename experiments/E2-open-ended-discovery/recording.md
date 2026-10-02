# E2 完整机器记录（材料就绪，真人会话未运行）

操作员实际开始前按 session-setup.md 固定语言、翻译工具/设置、顺序和方法版本。
用户原话只由实际参加者提供；模型不能代填。文件保留本地，参与者使用 P01 等代号，
不记录姓名、邮箱、API key、私有项目内容或私人备注。

## 两个 JSONL 文件

- `sessions.jsonl` 每行一个会话，对应 schemas/e2-session.schema.json。
  未运行行保留原六个核心字段，status=未运行/owner-blocked；不能附已经观察到的结果。
  status=recorded 时必须补全翻译工具/设置/目标语言、时区明确的起止时间、顺序、
  起点、兴趣、方法版本、打开项目、是否值得继续及理由、放弃原因、准备时间、
  GitHub/模型请求次数、可见成本、观察员记录；不知道的结果/次数/成本填 null。
  evidence_kind=human-record 仅用于真实发生的会话，测试只能用 fixture。
- `candidates.jsonl` 每行一个候选，对应 schemas/e2-candidate.schema.json。
  用 session_id 关联会话；保留来源链接/查询、方法版本、实际展示/名次、是否已知、
  before/after-recall/unknown、是否打开/值得继续、用户原话、期待用途、条件及未知项。
  observer_observation 与 generated_reason 分列，不能代替 reason_quote。
  未展示候选没有展示名次；真实反馈未知填 null，不按没有点击推断不相关。

候选仍需操作员核对属于哪个会话，来源是否公开、版本是否存在；CLI 的结构检查
不能证明内容真实，也不验证第三方许可。schema 约束字段；CLI 另外检查时间顺序、
翻译目标、未知状态、重复会话与成对比较条件。

```sh
python3 scripts/stage_records.py session /path/to/sessions.jsonl
python3 scripts/stage_records.py candidate /path/to/candidates.jsonl
```

会话汇总分别列出真人、fixture 与未运行数量；fixture 不进入真人配对比较。
缺少 A/B 条件、翻译基线不同、语言/顺序不一致或时间重叠会标记配对不可比。
comparable_structure 仅表示结构可比，不是正效果、充分样本或统计显著性结论。
费用 null 不会变成零成本。工具不补造邀请、会话、判断或回访记录。
