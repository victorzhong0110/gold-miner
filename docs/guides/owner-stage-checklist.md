# 本阶段交给发起人的操作与决定

更新于2026-10-05。统一 MIT 已按你的选择落实。以下事项需要你的账户、体验、参与者或判断；
自动测试和合并代码不能代替它们。没有要求你重新审查工程细节或重复批准已授权合并。

**2026-10-05 新增：你 2026-10-04 首轮真机操作报的问题（S1–S6）已全部修完**，
逐项修法与回归位置见 [会话问题清单](../session-issues.md#2026-10-05-批量修复结果)。
其中 S6 是阻塞项：修复前模型路径**实际从未真正运行**（`max_tokens=256` 让推理模型
把预算全花在思考上，JSON 未输出就截断），而选项页绿灯、终端探测都显示成功。
现在探测会校验模型是否真的产出了内容。

**模型路径已用你的本机凭据做过真机验证**（2026-10-05，真实 `MiniMax-M3` 请求，
`finish_reason: stop`，解析出 4 条中英扩展，
[记录](../reports/2026-10-05-live-model-verification.md)）。顺带修正一处你的观察：
256 不是「一直坏」而是**临界值**——三条查询里挂两条，所以表现得像「模型时好时坏」。

因此第 1、2 项仍需你重装后确认，但重点变了：**不再需要你判断「模型通不通」**，
而是要看 O1 那条观察——带可用模型重跑 `剪贴板历史 管理器`，
记录模型请求次数（不得为 0）、候选来源分布、面板结果与 GitHub 原生搜索的重合度。
这是目前唯一能回答「扩展到底有没有用」的入口。

| 顺序 | 你的操作 | 记录与完成标准 |
|---|---|---|
| 1 | 在自己的 Chrome 加载 dist/gold-miner-extension 目录，保存阅读语言/兴趣；配置你愿意使用的模型端点、模型和密钥并授权端点 | [上手](getting-started.md)；记录浏览器、版本、端点域名/模型、探测结果，不记录密钥 |
| 2 | 试一次中英搜索和仓库探索，取消/关闭/导航；在另一个浏览器配置目录导入缓存 | 搜索是否满足真实需要；导出无密钥；版本变化是否重新获取；与 CI fixture 证据分开 |
| 3 | 选择正式评估模型后，**重新冻结**材料（现有四个指针指向的提交缺 M 组提示词与种子集，冻结不成立），再跑 E1 B/C/M 与强对照 D | [冻结检查清单](../experiments/E1-cross-language-search/freeze-checklist.md)；[离线/实验操作](../engineering/offline-operator.md)；真实模型请求可能计费；不从 A-only 推断增益；记录真实等待与可见费用 |
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

**第 3 项新增一件必须先做的事**：已登记的评估冻结**不成立**——四个 SHA 指针都指向
`6010be0e`，但那个提交里没有 M 组提示词（`m-rewrite.txt`）也没有 `verified-seeds.jsonl`。
M 组是四个实验臂之一。现在直接跑，M 组结果会来自一个从未冻结的提示词，事后无法察觉。
自动核对已就位（`status: stale`），选定模型后另开一个提交把四个指针重新指向
确实包含全部材料的提交即可；**在此之前本批不能称为「已冻结」**。

你完成实际操作后交回去除密钥和私人信息的错误现象、JSONL 和判断，后续工程修复
可以据此继续；不需要用猜测或空白表单冒充已运行结果。

E2 完整字段及操作说明见 [记录说明](../../experiments/E2-open-ended-discovery/recording.md)。结构验证会保留未知、排除 fixture 的真人计数，并标记不完整/条件不一致的配对；不能代替你的真实判断。

E3 已补 [三轮短摘录上下文与代码材料](../../experiments/E3-faithful-reading/context-pack-2026-10-03.md)；正式比较前由你冻结选定范围和工具。两种条件须使用相同的原语言 quote、代码及 authored_context，不把作者说明当成机器译文；整页或图像比较须另行登记范围。
