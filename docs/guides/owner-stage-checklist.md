# 本阶段交给发起人的操作与决定

更新于2026-10-03。统一 MIT 已按你的选择落实。以下事项需要你的账户、体验、参与者或判断；
自动测试和合并代码不能代替它们。没有要求你重新审查工程细节或重复批准已授权合并。

| 顺序 | 你的操作 | 记录与完成标准 |
|---|---|---|
| 1 | 在自己的 Chrome 加载 dist/gold-miner-extension 目录，保存阅读语言/兴趣；配置你愿意使用的模型端点、模型和密钥并授权端点 | [上手](getting-started.md)；记录浏览器、版本、端点域名/模型、探测结果，不记录密钥 |
| 2 | 试一次中英搜索和仓库探索，取消/关闭/导航；在另一个浏览器配置目录导入缓存 | 搜索是否满足真实需要；导出无密钥；版本变化是否重新获取；与 CI fixture 证据分开 |
| 3 | 选择并冻结正式评估模型、既有代码 SHA、检索批次和判断标准，再跑 E1 B/C/M 与强对照 D | [离线/实验操作](../engineering/offline-operator.md)；真实模型请求可能计费；不从 A-only 推断增益；记录真实等待与可见费用 |
| 4 | 安排 E2 两对自检、4–6 人探索/盲判，以及 E3 两种现成翻译界面的阅读对照 | 按既有 protocol；参与者自愿；保留实际理由、未知项和失败，不替参与者回答 |
| 5 | 自行决定是否发出试用邀请，目标 10–20 人；逐日记录约一周并回访 | 未代发邀请；[E7 记录格式](../../experiments/E7-continuous-use/README.md)，本地验证命令见下 |
| 6 | 有实际证据后分别决定搜索、探索和翻译方向继续、缩小或暂停；是否采用元数据草案与改名由你判断 | [阶段报告](../reports/2026-10-02-phase-review.md)；没有证据时保留未决定；商店上架不在本阶段授权内 |

```sh
python3 scripts/stage_records.py discovery experiments/E5-local-reuse/discovery-entries.jsonl
python3 scripts/stage_records.py diary /path/to/your-local-diary.jsonl --timezone Asia/Taipei
python3 scripts/stage_records.py session /path/to/your-local-sessions.jsonl
python3 scripts/stage_records.py candidate /path/to/your-local-candidates.jsonl
```

最小发现条目已提供规范地址、双语用途、别名、类型、条件、来源文件/提交/时间、
生成状态与未知项。当前条目来源为本项目自有 README，文本为待人工审核的概述；
不是对项目有用性的评估结论。贡献开关默认为关闭，第三方条目须先核对来源许可。

你完成实际操作后交回去除密钥和私人信息的错误现象、JSONL 和判断，后续工程修复
可以据此继续；不需要用猜测或空白表单冒充已运行结果。

E2 完整字段及操作说明见 [记录说明](../../experiments/E2-open-ended-discovery/recording.md)。结构验证会保留未知、排除 fixture 的真人计数，并标记不完整/条件不一致的配对；不能代替你的真实判断。

E3 已补 [三轮短摘录上下文与代码材料](../../experiments/E3-faithful-reading/context-pack-2026-10-03.md)；正式比较前由你冻结选定范围和工具。两种条件须使用相同的原语言 quote、代码及 authored_context，不把作者说明当成机器译文；整页或图像比较须另行登记范围。
