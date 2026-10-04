# WP1–WP6 状态与交接

更新：2026-10-02。用户已授权继续本阶段全部工作，并明确要求该合的 PR 合、该关的 PR 关。唯一写入者：当前 ChatGPT Work 会话的 Codex；没有派发其他代理。

执行工作区：`/workspace/scratch/391b610db106/gold-miner`，分支：`work/phase-completion-2026-10-02`。起始 main：`8d7b951eaa56bf8a26f99dac14b8175a62b52c09`。整合 #2–#9 的实现和材料；#4 的旧重复实现保留新版本，独有历史证据已取入。

R1（模型缓存恢复）、R2（取消终态）、R3（导入链接）已修复并有连续操作回归。验证入口：`python3 scripts/run_offline_suite.py`。构建入口：`bash extension/scripts/build.sh`；产物与源码逐文件校验，源码 SHA 和 ZIP 哈希在 `dist/build-manifest.json`。

实现、离线验证、提交与合并不代表真实产品效果验收。**整个阶段尚未全部验收**：E1 模型实跑已完成；本人 Chrome 安装复测与真人会话/盲判/持续使用仍待验收。MIT 已由发起人选择并落地。Chromium fixture 自动验收已通过；它不等于真人安装或 GitHub 实际效果。状态 `verified` 表示相应工程子项经离线验证，其余子项分别列明缺口。

最新机器记录：[phase-status-2026-10-02.json](phase-status-2026-10-02.json)。阶段报告：[2026-10-02-phase-review.md](../reports/2026-10-02-phase-review.md)。远端已核对：[#10](https://github.com/victorzhong0110/gold-miner/pull/10) 在 CI 通过后合并，合并提交 `b93f89ee02841c25a9f9917345a4e5be77a9fb17`；#2–#9 已全部 closed/merged，当时没有遗留开放 PR。合并后 main 复验 243 项 Python + 45 项 Node 通过；合并状态不改变表中未完成的实际验收。

| ID | 任务 | 状态 | 本轮证据或未完成原因 |
|---|---|---|---|
| WP1-01 | 核对基线与交接 | verified | 独立工作区、唯一写入者、基线与 PR 祖先已核对 |
| WP1-02 | 对齐协议与规范 | verified | 规范入口显式对齐；历史 v0.3/v0.4 未改 |
| WP1-03 | 真实模型客户端和配置 | verified | MiniMax-M3 真实 B/C/M 60 次调用已记录；超时/认证/解析回归通过；个人 Chrome 复测单列 WP3 |
| WP1-04 | 接通完整检索执行链 | verified | e1_pipeline.py + test_e1_pipeline.py：保留原文、语言标签、预算和字段检查 |
| WP1-05 | 冻结评估材料 | verified | 2026-10-04 设置冻结于已存在 ae5eeea；运行源码 48b074d 仅新增设置；题目/提示词/种子哈希全匹配 |
| WP1-06 | 准备 E2/E3 正式材料 | partial | E2 会话包、E3 真实片段已保留；正式多轮材料和实际会话待补 |
| WP1-07 | 离线基线与操作说明 | verified | 统一离线套件含 E6/E8/内容脚本/源码与包一致性 |
| WP2-01 | 预先登记判断标准 | verified | 判定口径、预算、字段、排序与失败处理预先保留；本次模型/设置在运行前冻结，未改判断门槛 |
| WP2-02 | 运行 E1 A/B/C/M | verified | MiniMax-M3 全批 A/B/C/M 已运行并保存 60 模型/208 GitHub 请求，1 GitHub422、1解析失败未重跑；人工判断归 WP2-04 |
| WP2-03 | 运行强对照 D | verified | MiniMax-M3 D 全批 20 题已运行并审查，169 仓库存在；人工判断归 WP2-04 |
| WP2-04 | 盲判和增量分析 | partial | 五组前5来源遮蔽材料已生成：233 题目/仓库组合、311 组内位置；真人判断未运行 |
| WP2-05 | 运行 E2a | pending-human | 两对自检及 4–6 人会话未发生 |
| WP2-06 | 运行 E3 基线 | partial | 六条 gtx 输出与技术核对已保留；两种翻译界面对照待测 |
| WP2-07 | 必要时 E9 诊断 | conditional | E9 只在增益诊断需要时执行；目前无正式比较可诊断 |
| WP2-08 | 首轮决策 | pending-evidence | 已有未决定报告，不能从 A-only 结果推出跨语言增益 |
| WP3-01 | 审查整合现有扩展 | verified | 整合 #2–#9；保留 #4 独有历史记录；R1/R2/R3 回归通过 |
| WP3-02 | 完成首次使用流程 | partial | Chromium 设置页保存/语言/兴趣通过；sender.tab 真实缺陷已修；个人 BYOK 配置和提供商实测留给发起人 |
| WP3-03 | 原页面搜索与预览 | partial | 真实 Chromium 内容脚本和规范链接通过；DOM/HTTP 为 fixture，真实 GitHub 与个人价值待验收 |
| WP3-04 | 仓库页探索 | partial | Chromium 仓库探索与页面导航通过；来源为 fixture，实际获取价值留给真人 |
| WP3-05 | 安全边界与导入链接 | verified | 受信存储、特权消息隔离、端点及导入链接回归通过 |
| WP3-06 | 导航与任务生命周期 | verified | 取消、迟到回调、关闭、导航离开、重复事件、并发、清空数据回归通过 |
| WP3-07 | 实机验收 | partial | 真实 Chromium MV3 自动加载、选项/内容脚本/存储隔离等8项通过；个人 Chrome 安装与真人体验留给发起人 |
| WP3-08 | 首次外部安装 | pending-human | 首次外部安装需要真实参与者；未发送邀请 |
| WP4-01 | 开放候选来源 | partial | 开放获取来源已实现；价值不能由 fixture 推出 |
| WP4-02 | 规则排序与多样性 | verified | 探索余量实际引入其他来源；去重、已见过滤和作者上限有回归 |
| WP4-03 | E2b 自动推荐验证 | pending-human | E2b 同池排序和新起点获取比较需要真实判定 |
| WP4-04 | 轻量个性化 | partial | 兴趣、反馈、开关及重置已验证；可选历史仅本地记录，未宣称用于推荐 |
| WP4-05 | 缓存与模型模式切换 | verified | 模型恢复/切换、24h 过期、README 内容指纹、无分隔符碰撞缓存键 |
| WP4-06 | 预算、取消和并发 | verified | 每任务最多4次 GitHub、最多1次模型；2个并发任务；取消、限流退避和清空回归 |
| WP4-07 | 成本等待报告 | partial | 实际发送次数与缓存命中计量已接入；真实模型成本/等待仍未知 |
| WP5-01 | 试用交付准备 | verified | 中英说明、0.1.2 试验包、确定性构建、版本与已知限制齐备 |
| WP5-02 | 招募与首次体验 | pending-human | 10–20 名志愿者未招募；无邀请发送授权，未发送 |
| WP5-03 | 持续使用 E7 | pending-time | E7 一周日记未发生，不能在单次执行中压缩成真实一周 |
| WP5-04 | 优先修使用障碍 | pending-evidence | 已修工程缺陷；真实试用障碍与回访须由反馈产生 |
| WP5-05 | 第二环境复用 E5 | partial | 两个独立 Chromium 配置目录的 UI 导出/导入、0额外请求命中及内容变化重新获取通过；真实数据成本复用留给发起人 |
| WP5-06 | 最小发现条目 | verified | 双语 JSONL、规范地址、来源提交/文件、生成状态、未知项和关闭的贡献开关已验证；实际价值未评估 |
| WP5-07 | 共享与翻译条件分支 | conditional | 本地复用可测；公共托管/共享译文无节省证据，暂不扩大 |
| WP6-01 | 新材料复测与稳定性 | partial | 新失败情景回归通过；未用于开发的新题效果复测未执行 |
| WP6-02 | 许可证与开源准备 | verified | 发起人选择统一 MIT；根 LICENSE、第三方声明和分发包许可已落实 |
| WP6-03 | Beta交付 | partial | 0.1.2 源码/ZIP/许可哈希一致，Chromium fixture 自动验收通过；真人试用未验收，仍为试验包 |
| WP6-04 | E8 搜到黄金矿工 | partial | 历史 E8 检索与元数据草案已保留；应用元数据后三入口复测待执行 |
| WP6-05 | 名称和入口判断 | conditional | 工作名沿用；没有足够混淆证据，不改仓库名 |
| WP6-06 | 可选商店上架 | out-of-scope | 可选商店上架未获授权，且用户对外预算为零 |
| WP6-07 | 三个月决策 | partial | 分方向阶段报告已更新，搜索/探索/翻译效果尚未决定 |
| WP6-08 | 维护交接 | verified | 45 项状态、唯一负责人、源码/包/验证与明确阻塞已登记；不自动开新阶段 |

本轮续作：MIT 决定已落实，E7 记录工具及 WP5-06 双语发现条目已完成。实际 Chromium fixture 自动验收已加入 CI，尚待本轮远端运行；不等于真人安装或实际效果。需你决定和亲自操作的事项见 [操作清单](../guides/owner-stage-checklist.md)。

Chromium 首跑发现真实设置页消息带有 sender.tab，旧权限判断使保存被拒绝；0.1.2 按自有扩展 URL 授权设置页，拒绝内容脚本及其他页面特权消息。新增回归后离线复验：251 Python + 46 Node；浏览器第二轮待跑。此前 243 Python 统计漏掉 E5 的单项测试，原日志实际为 244，历史原日志保留。

最新浏览器证据：[8项真实 Chromium fixture 验收](../reports/browser-acceptance-2026-10-02.json)，[CI 37026709955](https://github.com/victorzhong0110/gold-miner/actions/runs/37026709955) 全部通过。0.1.2 修复已通过；前述「待跑」为首跑/修复时的历史状态。当前续作交付为 [PR12](https://github.com/victorzhong0110/gold-miner/pull/12)，合并状态以该 GitHub 记录为准。剩余个人操作与决策只按 [发起人清单](../guides/owner-stage-checklist.md) 进行，不虚构完成。

## 2026-10-03 续作

[PR12](https://github.com/victorzhong0110/gold-miner/pull/12) 已合并，合并 main 为
96318eab0c4f7d90f75bcf27b4073cb4307c7d25。本轮在此基线上复现并修复四个并发写入问题，
增加失败反馈可重试界面、完整 E2 会话/候选 schema 与验证工具，以及日记观察者时区。
[具体报告](../reports/2026-10-03-storage-and-records.md)。新版 0.1.3 离线267 Python + 53 Node 通过，
新增浏览器并发验收已通过，9项检查全绿（[记录](../reports/browser-acceptance-2026-10-03.json)）。真人记录与效果判断未发生；E3 三轮短摘录上下文、代码注释和双向原文材料已补齐（不含整页/图像档案）；实际冻结、翻译和评判未运行。

当前续作交付为 [PR13](https://github.com/victorzhong0110/gold-miner/pull/13)，合并状态以 GitHub 记录为准。0.1.3 源码、安装包及浏览器生产脚本哈希已核对一致；需要发起人亲自操作和决定的范围保持不变。

## 2026-10-04 真机反馈

已读取独立反馈分支的docs/session-issues.md。0.1.4修复S1/S3/S5/S6，S2保留官方大陆端点并补来源/区域说明；268 Python + 58 Node离线通过，11项Chromium fixture已通过，记录见docs/reports/browser-acceptance-2026-10-04.json，交付[PR14](https://github.com/victorzhong0110/gold-miner/pull/14)，合并状态以GitHub为准。S4强对照D工具/模型/预算仍由发起人决定，没有运行或效果证据。[修复说明](../reports/2026-10-04-runtime-fixes.md)。

## 2026-10-04 D 组决定

发起人已选定 MiniMax-M3，且不设 D 组任务上限，见 [0004](../decisions/0004-minimax-d-group.md)。第一次执行实跑入口时进程环境缺密钥，未发送请求；随后带密钥实跑 `runs/2026-10-04-d-minimax/`。首轮 3 题失败（2 超时、1 HTTP 400），修正 runner（失败题不算完成、可续跑重试；GitHub 301 跟随为改名后的仓库）后续跑，3 题各重试 1 次成功。结果：20/20 题完成，模型请求 23，GitHub 核对 177，提名 172，存在 169（3 个经 301 跟随），404 幻觉 3（1.7%），与 2026-09-22 A 组集合交集 0。这是名单是否存在的核对，不是用途适合度；人工判断、B/C/M 在本模型上未运行，费用未知。[记录](../reports/2026-10-04-e1-d-run.json)，[报告](../../experiments/E1-cross-language-search/runs/2026-10-04-d-minimax/report.md)。

## D组审查后续

PR15已合并（065ff0605cac5f641c5fd6511bda34bf8f11397a），原始记录未修改。逐题prompt/input哈希及统计离线核对一致；修复续跑混入参数/题集、截断答案被当成功、取消输出上限重发的路径。B/C/M已补2048token/思考剥离/截断拒绝，默认60秒（环境可覆盖）；未调用实际模型。机器账本已同步D实跑状态，人工用途判断仍未运行。

本次续作完整离线296 Python + 58 Node通过（docs/reports/bcm-validation-2026-10-04.json）；付费请求0。B/C/M入口要求独立run-id和新输出目录，保留源码SHA/配置哈希；实际运行与人工判断留在发起人环境。

## 2026-10-04 A/B/C/M 实跑

2026-10-04 A/B/C/M 已用 MiniMax-M3 实跑 eval.batch_1（`runs/2026-10-04-bcm-minimax`，冻结设置 `run-settings-2026-10-04-bcm-minimax.json`，源码 SHA 48b074d）：A 20/20、B 19 完成+1 部分（GitHub 422）、C 19 完成+1 阻断（模型输出 JSON 解析失败）、M 20/20；模型请求 60，GitHub 请求 208（失败 1）；题级合并候选 A70/B212/C323/M127，与同日 D 组仓库题级交集 A0/B2/C9/M0。人工用途判断未运行，费用未知，不下跨语言增益结论。

运行前修复并提交（ae5eeea）：GitHub 搜索间隔原为 0（会超过每分钟 30 次限额）、输出目录非空即拒绝（保护 D 目录）、冻结设置与客户端参数核对、记录可见 token/耗时。冻结设置提交 48b074d（BYOK_TIMEOUT_SECONDS=300，2048 输出 token，不自动重试，无密钥）。失败未重跑：B zh2en-eval-10 长句直译 GitHub 422；C en2zh-eval-03 模型输出 JSON 解析失败（原文未保存）。可见 token：B 输入8330/输出1989，C 10894/4714，M 10170/4834；费用未知。[报告](../../experiments/E1-cross-language-search/runs/2026-10-04-bcm-minimax/report.md)，[机器记录](../reports/2026-10-04-e1-bcm-run.json)。WP2-04 盲判仍待发起人。

2026-10-04 PR17 审查：原始记录与冻结设置一致；A/B/C/M 题级并集465，跨题独立仓库391，与D独立仓库169交集9。已准备五组前5判定材料（evaluation/2026-10-04-minimax），人工判断尚未发生。没有重跑失败项或新增付费请求。

## 2026-10-05 B/C/M 失败证据补齐

复核 `runs/2026-10-04-bcm-minimax` 时发现 C 组 `en2zh-eval-03` 的失败记录
**没有保存模型原文**（232 completion token，其中 171 思考），因此无法判断
失败是散文包裹、schema 不匹配、拒绝还是截断；而协议禁止把失败项重跑进同一批次，
证据只有第一次机会。

已修两点，记录见 [2026-10-05-bcm-failure-evidence.md](../reports/2026-10-05-bcm-failure-evidence.md)：

1. 失败时按 D 组已有做法保存脱敏、限长的模型原文（`raw_output_sha256`、
   `raw_output_chars`、`think_present`、`answer_text`、`raw_output`），
   **不改变解析行为**，故不影响已完成运行的有效性；成功路径不写这些字段。
2. 顺带修掉 `_extract_json_object` 用 `find("{")`/`rfind("}")` 的取法：
   只有一个花括号组时正常，但模型同时给示例和答案时会把示例内容当真实查询记进
   候选集且不留痕迹。改为数顶层平衡括号组，多于一个即报 `ambiguous_model_output` 拒绝猜。
   C 组提示词禁止输出散文，合规回复行为不变。

**已回头审计两个已完成运行**（`2026-10-04-bcm-minimax` 60 条生成记录、
`2026-10-04-d-minimax`）：未发现散文污染，初筛 6 条命中全为误报
（`zh2en-eval-09` 的 "todo" 是正常应用名，两条「超长」是 B 组忠实翻译）。
**既有结论不因此改变。** `en2zh-eval-03` C 组那一题的具体失败原因仍不可知，不作猜测。

验证：离线套件 exit 0，**316 Python + 58 Node**（原 305 + 58），全程付费请求 0。

## 2026-10-05 盲判材料遮蔽强度实测

判定尚未发生（`runs/2026-10-04-bcm-minimax/judgments.jsonl` 仍为空）时，
审计了 `evaluation/2026-10-04-minimax/` 这批材料的遮蔽强度。

`blind_eval.py:40` 的 `blind_id = sha256(run_id + ':' + task_id + ':' + repo)[:16]`
**不含 arm**（blind_id 同时充当去重键），而这三个输入值都公开可读，
因此**不打开 `blind-key.json` 也能重算分组**。实测 233 个 blind_id 中
**196 个（84%）可确定归属单一组**，A 组 4/4 全部暴露、D 组 95 条可确定。

材料 README 原先把风险写成「映射在同一仓库，判定人可能去翻」，
把问题说轻了：真实情况是跑一条命令即可还原，与自觉无关。
已新增 `blind_eval.py --audit-masking` 让工具自报强度（不读 key、不写判定材料），
并把披露改成实际量级。详见
[2026-10-05-blind-masking-audit.md](../reports/2026-10-05-blind-masking-audit.md)。

**真正遮蔽需要不存放在本仓库的私密 salt。机制已就绪，选择权留给发起人**：
`E1_BLIND_SALT` 环境变量或 `--salt-file` 读取（不走 argv，避免进 `ps` 与 shell 历史），
`--key-out` 让映射表落在仓库外。实测加 salt 后仅凭公开数据可确定归属
从 196/233 降到 0/233。无 salt 时现有材料仍逐字节可重建，故加 salt 是显式选择。
本轮**不生成 salt、不写假 salt 充数**。

**salt 挡不住主动翻 key 的人**，只保证「仅凭公开数据无法反推」；
在此之前 WP2-04 的判定结论只能写成「带已知可还原分组属性的来源遮蔽判定」，不能写成盲判。

验证：离线套件 exit 0，**326 Python + 58 Node**（原 316 + 58），付费请求 0。
过程中自查出并修正一处自身缺陷：审计最初把 salt 传给了「攻击者」的重算，
导致加 salt 后仍报 196 可还原——威胁模型应为「持有公开数据但没有 salt 的人」。

## 2026-10-05 提示词与 pipeline 查询规则矛盾（潜在失败）

`runs/2026-10-04-bcm-minimax/report.md` 的「不能下的结论」里记了一条一直没处理的
矛盾，本轮把它查实并加了防再犯的检查。

`prompts/c-rewrite.txt:13` 明确许可 `in:description` 与 `stars`
（「需要限定字段时只用 in:description；stars 可用」），
而 `e1_pipeline.py:31-32` 对 `in:`/`stars:`/`language:`/`repo:`/`user:`/`org:`
一律 `raise ValueError`。**模型照提示词做才是错的，失败却会记成模型错误。**
三组里只有 C 许可（B 是「不准加任何…等」全面禁止）；
M 只列了三个限定符，`in:description`/`repo:`/`user:`/`org:` 完全未提。

pipeline 的规则是对的：基线 A 是无限定符默认搜索，若任一组能用字段或 stars
限定，各组搜索空间不同，集合差就不再衡量跨语言改写，与 AGENTS.md 第 23 条
「不设 stars 下限」方向也相反。

prompts 是冻结材料（protocol：修复另开 `eval.batch_2`），**本轮不修**，
归属发起人。本轮做的是让矛盾无法被忽略：新增 `e1_materials_check.py`
与 `test_e1_materials_check.py`（10 项），并在 `materials-status.json`
以 `file:line` + 原文引用记录意图级判断，由测试断言该行至今未变——
提示词一旦被修正，测试立即失败并逼迫更新记录。棘轮双向验证通过。

**过程中推翻重写了自己第一版检查器**：它从中文散文猜「允许/禁止」，
把 C 的「本步不要写 in:readme」和 M 的「不准加…stars:」都判成允许——
若照单全收就会去修两个不存在的问题。新版只报告机械可验证的
「是否提到」，不再输出意图判断。

验证：离线套件 exit 0，**336 Python + 58 Node**，付费请求 0。
已完成两个运行均未触发该矛盾，结论不变。详见
[2026-10-05-prompt-pipeline-contradiction.md](../reports/2026-10-05-prompt-pipeline-contradiction.md)。

## 2026-10-05 A/B/C/M 运行缺 failures.jsonl

记录形状不一致：D 组运行写 `failures.jsonl`，A/B/C/M 不写，
而 `schemas/failures.schema.json` 定义了该文件。后果是同一个实验的两类记录
形状不同，消费方要为 A/B/C/M 特判。

**先澄清：失败信息没有丢**，逐任务失败本来就在 `pipeline.json` 里机器可读
（B `zh2en-eval-10` 的 422 带 `api_query`、C `en2zh-eval-03` 的 blocked 带 `reason`）。
问题是「schema 规定的独立账本没生成」，不是「无法诊断」。

`e1_pipeline.py:194` 早已检测失败并据此返回 exit 2，却只交给退出码、不落盘。
已新增 `failure_rows(result)` 并在 `main()` 写出 `failures.jsonl`：字段全部取自
已有的 `generation_records` 与 per-task `status`/`errors`/`reason`，不编造；
遵守 `additionalProperties: false`，一行仅 `run_id`/`task_id`/`arm`/`code`/`message`
（出问题的 `api_query` 留在 `pipeline.json`）；**空也写文件**，因为缺文件与
「跑过但没失败」无法区分。

从已记录的 `2026-10-04-bcm-minimax` 派生的 3 行显示：一次查询生成失败会让同一
`task_id` 出现两行（`bad_response` 与 `blocked`，两个层次），**行数不等于失败任务数**，
统计须去重 `task_id`。

**没有回填历史运行**：那次运行没产生该文件，事后补等于伪造记录。
本条只对后续运行生效，历史运行的失败仍从 `pipeline.json` 读。

**顺带发现、本轮不改**：`:194` 判定失败不含 `tasks_partial`，
即只有 partial 而 `failed_requests` 为 0 时会 exit 0 却有账本行，口径不一致。
是否让 partial 也算失败属发起人决定。详见
[2026-10-05-failures-ledger-gap.md](../reports/2026-10-05-failures-ledger-gap.md)。

验证：离线套件 exit 0，**343 Python + 58 Node**（原 336 + 58），付费请求 0。

## 2026-10-05 判定分析漏了协议要求的 B→C

盲判材料即将由发起人判定，`blind_eval.py analyze` 是判定后立刻要跑的一步。
核对其产出与协议第 6 节要求，发现对不上。

协议第 6 节要求三个比较：`**A→C** 衡量整体辅助效果；**M→C** 更接近相同预算下的
语言扩展贡献；**B→C** 判断复杂程度是否值得」。修前只产出 `c_minus_a` 与
`c_minus_m`，**`c_minus_b` 不存在**——而 B→C 正是「这套复杂度值不值得」那个
产品决策的直接答案。B 的 `suitable` 其实早已算出（`groups['<task>:B']`），
只是没参与差集。

更严重的是**「完整」标签过宽**：修前只有一个总开关，只看 A/C/M，**完全不看 B**。
一个任务 B 组判定全部缺失时，A→C 与 M→C 照样标成 `complete`，
给出了它没有兑现的保证。

已改为**每个比较项各自带完整性**：`c_minus_a`/`c_minus_m`/`c_minus_b` 各自
判断所需两臂是否完整，不完整写 `{'status':'incomplete-no-comparison','needs':[...]}`
而**绝不写空列表**（空列表会被读成「这组没有独有合适候选」，那是结论）。
B 缺失只影响 B→C，不连累 A→C 与 M→C。**D 刻意不做差集**——它走联网助手、
请求预算不同（模型请求 23 vs 60），协议明确 D 是子集试用不与全量平均混用；
D 的逐任务集合仍在 `groups` 里可见，并新增 `d_not_differenced` 说明。
每项带 `protocol_basis: 'E1 protocol section 6'` 使映射可核对。

**用已记录运行的真实任务状态核对（判定内容为模拟，只看结构可得性，非结果）**：
`zh2en-eval-10`（B partial，GitHub 422）失去 B→C；`en2zh-eval-03`（C blocked，
模型 JSON 解析失败）三项全失。**20 题里 13 题至少有一项比较不可得**，
即这批材料最多在约 7 题上给出完整三项比较。是否值得按此规模判定属发起人决定。

验证：离线套件 exit 0，**347 Python + 58 Node**（原 343 + 58），付费请求 0。
`product_effect` 仍为 `not-concluded`，判定材料与既有运行记录均未改动。详见
[2026-10-05-analysis-missing-b-comparison.md](../reports/2026-10-05-analysis-missing-b-comparison.md)。

## 2026-10-05 更正：B 组查询长度的三条推断已撤回

上一节（B→C 比较含已测量的查询长度混淆）写入的三条推断
**已被实跑数据否证，现撤回**：

1. 「B 组查询与 GitHub 关键词检索结构性不匹配」——撤回
2. 「C−B 被查询长度污染」——撤回
3. 「B 这一臂被实现成了稻草人」——**与数据相反**

否证数据（`2026-10-04-bcm-minimax`）：

| 组 | 跨题去重仓库 | 合并候选 | per-query（其中生成查询） |
|---|---|---|---|
| A | 51 | 70 | 70（0） |
| **B** | **156** | 212 | 242（**172**） |

`B − A = 106`（`A − B = 1`）。**B 贡献的仓库是 A 的三倍，其中 106 个 A 没有**，
不可能是稻草人。逐题看，**11/20 题**的 B 译句查询返回 ≥1 条；
返回 0 的 9 题里有 4 题长度仅 13–21 字符——短查询同样返回 0。

根因是我的探针同时操纵了两个变量：把 193 字符的**完整句子**按词边界截断，
截断后语义破碎，141/86/65 字符那几行的 0–1 条结果测的是
「半句话检索不到」，不是「长查询检索不到」。

**唯一仍然成立的一条**：`zh2en-eval-10` 那条 193 字符查询可复现返回
HTTP 422，为 20 题中的 1 题，该题 `status=partial`。除此之外没有证据表明
B 组存在系统性长度劣势。

保留这份记录而非悄悄改掉，是为了让下次有人想用「B 查询太长」解释 C−B 数字时，
先撞见「试过，被否了」。可复用教训：**当探针本身改变了被测对象，
测出的差异不能归因于你正在操纵的那个变量。**
完整记录见 [2026-10-05-b-arm-query-length-confound.md](../reports/2026-10-05-b-arm-query-length-confound.md)（该文件已改写为自我推翻记录）。

## 2026-10-05 A/B/C/M 无法产出 latency_cost.jsonl（耗时从未被测量）

把 4 个已记录运行逐个按 schema 校验：**1862 行、0 违规**，记录形状本身健康。
但 `latency-cost.schema.json` 存在而只有 D 组写了对应文件，A/B/C/M 三个都没有。

根因不是忘了写文件，而是**需要的那个数从来没被采集**：
`e1_pipeline` 写文件前只有 `started_at`/`finished_at` 两个整轮时间戳，
全文件没有 `time.monotonic()`；每个 (task, arm) 格子的两半——
模型生成 `generate(...)` 与 `run_batch` 内的逐题检索——都没计时。
所以 `elapsed_ms` 没有数据来源，直接造文件只能填 0，那比不写更糟
（会让人以为「耗时为零」）。

影响：协议第 6 节六项观察项之一的「**成本与等待**」中的「耗时」这一半
在任何记录里都不存在；WP4-07 停在 `partial` 的理由「真实模型成本/等待未知」
与此一致。本次的 `model_usage` 有 token 计数（B 输入 8330 / 输出 1989 等），
但无逐题耗时。

已修（先测量再写文件）：
- `e1_batch.run_batch` 在正常路径、`except` 异常路径、取消路径三处都写回
  `elapsed_ms`（取消路径为 0，因为没干活）
- `e1_pipeline.run_pipeline` 对每次 `generate(...)` 计时并按 (task, arm) 累积
- 新增 `latency_cost_rows()`，每 (task, arm) 一行，
  `elapsed_ms` = 检索 + 生成；`github_requests` 取已有 `attempted_requests`；
  `model_requests` 复用 `summarize_usage` 的 `request_parameters` 判据；
  `main()` 写出 `latency_cost.jsonl`（空也写）
- **`visible_cost` 一律不编造**：live 写 `unknown`、fixture 写
  `fixture-no-model-calls`，与已有 `model_cost: "unknown"` 一致

**未回填历史运行**：三次旧运行的耗时从未被测量，补一个全 0 的文件等于宣称
当时耗时为零。已确认 `runs/` 零改动。从旧 `pipeline.json` 只读导出形状为
80 行（20 题 × 4 臂）且 schema 全合法，但 `elapsed_ms` 全 0——正说明不能回填。

验证：`test_e1_pipeline.py` 17 → 24 项，其中一项用会真的 sleep 的 stub 断言
`elapsed_ms > 0`（证明测的是真实经过时间而非占位 0）；实跑 fixture 得 40 行、
schema 全合法、四臂齐全；离线套件 exit 0，**354 Python + 58 Node**，付费请求 0。
详见 [2026-10-05-latency-cost-gap.md](../reports/2026-10-05-latency-cost-gap.md)。

## 2026-10-05 盲判记录无法通过仓库自己的 judgments schema

判定材料即将由发起人判定。核对「判定人产出什么形状的记录」时发现三方字段集不一致：

| 来源 | 字段 |
|---|---|
| `judgments.schema.json`（required, addProps:false） | 含 `run_id`/`task_id`/`repo`，**无** `blind_id` |
| `blind-sheet.md`（每项记录…） | 含 `blind_id`，**无** 那三个身份字段 |
| `blind_eval.analyze` 实际读取 | `blind_id` + 判定字段 |

差异两边对称：盲判行带 `blind_id` 会被 schema 的 `additionalProperties:false` 拒绝，
又缺三个必填身份字段。**即：发起人按判定表认真填完，得到的记录无法通过仓库唯一
声明权威的 schema**（`judgment-guide.md:41`「判定记录字段以本文件加 schemas 为准」）。
下游要么校验失败，要么绕过校验。

两边形状各自都合理——非盲判定天然知道 task/repo，盲判刻意只知道 `blind_id`。
缺的是把它们接起来的桥。

已修：

1. 新增 `schemas/judgments-blind.schema.json` 描述盲判输入的真实形状（10 字段，
   同为 addProps:false），并写明与 `judgments.schema.json` 的分工
2. 新增 `blind_eval.export_judgments(key, judgments, judge_kind)`：`run_id`/`task_id`/`repo`
   **从 `blind-key.json` 取**而非编造；导出形状与 `judgments.schema.json` 一致；
   **不写 arm**（留在 `groups` 供分析，不进记录）；`kind`/`notes` 缺失则**拒绝导出**，
   不填默认值——`analyze` 不读这两项但 schema 必填，替判定人填值等于伪造他的判断。
   实测导出全部通过 schema 校验且 arm 未泄漏
3. 三方漂移棘轮（7 项测试）：判定表字段集必须等于盲判 schema 的 required；
   `analyze` 读取的每个字段盲判 schema 都必须有描述；并显式断言「盲判行确实无法
   满足非盲 schema」。双向验证：临时从判定表删 `kind` → 测试失败；还原 → 27/27。

**未改判定材料**：`blind-sheet.md` 与 `evaluation/2026-10-04-minimax/` 一字未改
（棘轮验证的临时改动已还原）。它的字段集现在被测试**约束**而非被修改。

验证：离线套件 exit 0，**362 Python + 58 Node**（原 354 + 58），付费请求 0。
详见 [2026-10-05-blind-record-schema-mismatch.md](../reports/2026-10-05-blind-record-schema-mismatch.md)。

## 2026-10-05 E6 的 probe-record schema 不可满足

把「按 schema 校验已记录产物」从 E1 扩到 E2/E3/E6 时，在 E6 找到一个**比前两次
更严重**的问题：不是工具少产字段，而是 **schema 本身自相矛盾**。

`experiments/E6-api-probe/schemas/probe-record.schema.json` 的 `required` 有 **30** 个
字段名，`properties` 只描述 **16** 个，`additionalProperties` 却是 `false`。
那 14 个既 required 又不在 properties 里的字段
（`run_id`/`started_at`/`finished_at`/`base_url`/`model`/`protocol`/`prompt`/
`billing_note`/`response_format`/`visible_response_id`/`error_detail`/
`cache_hits`/`cancelled_before_send`/`max_output_tokens`）
**被同时要求与禁止——任何对象都无法满足该 schema。**

**为什么一直没发现**：`test_e6_probe.py` 里有一处
`self.assertEqual(set(record), set(schema["required"]))`，意图正确且一直通过
（工具确实产出 30 个、required 确实是 30 个），但它**只比对了字段名，
没有拿 schema 去过一遍记录**。差一步就能抓到。

**方向判断**：先确认哪边有问题——工具产出 30、schema required 30、
**schema 缺描述的必填字段为 0**（工具无任何 required 缺项），
即工具产出的是严格超集。那 14 个都是有价值的探测事实。
所以改 schema，不削工具。

已修：补齐 14 个字段声明（类型取自实测——今日新记录与 2026-09-22 已记录记录
形状一致），并给 `run_id` 补上 `minLength` 与说明（它本就在 required 里却连
描述都没有，而仓库另外 12 个 schema 都要求 run_id）。
`test_e6_probe.py` 新增两个模块级断言：`required - properties` 必须为空
（无需 jsonschema 即可跑），以及用 jsonschema 真验一遍记录（缺库时回退）。

验证：补声明前今日新记录 INVALID，补声明后 VALID，**2026-09-22 已记录记录也
VALID**（最强佐证：那份产物从头到尾都对，错的是 schema）；只带 30 个必填键的
最小对象 additionalProperties 错误 0；重新引入原缺陷测试失败、还原 14/14 通过；
**全仓库 13 个 schema 现已全部可满足**（E6 是唯一破损的）。
E3 的 observation.schema.json 有 9 个 required 未描述但 addl=true，不构成破损，
本轮不动。`e6_probe.py` 行为未改，只改 schema 与测试。

离线套件 exit 0，362 Python + 58 Node，付费请求 0，未改任何已记录产物。
E6 探测本身仍是「未运行」，本轮只修好它的记录契约。详见
[2026-10-05-e6-schema-unsatisfiable.md](../reports/2026-10-05-e6-schema-unsatisfiable.md)。

## 2026-10-05 schema 一致性扫描收口

把「按 schema 校验已记录产物」扩到 E2/E3/E5/E6/E8 后逐目录结案：

| 目录 | 结论 |
|---|---|
| E1 | 本会话已修 4 处（failures / latency_cost / judgments-blind / B→C） |
| **E6** | **真实缺陷：schema 不可满足，已修** |
| E3 | **一个假发现，已排除** |
| E2 | 无产物，会话未发生，符合预期 |
| E5 / E8 | 无 schema，但各有消费者自带检查，不存在被破坏的契约 |

**E3 的假发现**：`observations-2026-09-21.jsonl` 机械比对下不满足
`observation.schema.json`（有 `frag` 无 `frag_id`，缺 11 个必填字段）。
但 `test_observations.py` 文档字符串写明它是**「骨架完整且诚实为空」**的模板，
判定列全为 `未运行`——没有 `judge`/`judged_at` 正是诚实而非缺漏；真正的对照运行
是 `runs/2026-09-22-w6/observations.jsonl`，它**通过** schema。
若照机械结果动手「修」，会给一份刻意留空的模板补上伪造的 `judge`/`judged_at`，
正好违反「不得伪造实验结果、未运行就写未运行」。

**判别方法**（已写入记录）：机械比对易出假阳性，先分清
「已完成记录」还是「文档化的空模板」——看有无消费者、消费者是否声明按设计为空、
时间戳是否早于首次真实运行。三条都指向模板则不改，只记录。

**全仓库 13 个 schema 现已全部可满足。** 本轮未改任何已记录产物、
提示词或冻结材料。详见
[2026-10-05-schema-sweep-closeout.md](../reports/2026-10-05-schema-sweep-closeout.md)。
