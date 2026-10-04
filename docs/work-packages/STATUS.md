# WP1–WP6 状态与交接

更新：2026-10-02。用户已授权继续本阶段全部工作，并明确要求该合的 PR 合、该关的 PR 关。唯一写入者：当前 ChatGPT Work 会话的 Codex；没有派发其他代理。

执行工作区：`/workspace/scratch/391b610db106/gold-miner`，分支：`work/phase-completion-2026-10-02`。起始 main：`8d7b951eaa56bf8a26f99dac14b8175a62b52c09`。整合 #2–#9 的实现和材料；#4 的旧重复实现保留新版本，独有历史证据已取入。

R1（模型缓存恢复）、R2（取消终态）、R3（导入链接）已修复并有连续操作回归。验证入口：`python3 scripts/run_offline_suite.py`。构建入口：`bash extension/scripts/build.sh`；产物与源码逐文件校验，源码 SHA 和 ZIP 哈希在 `dist/build-manifest.json`。

实现、离线验证、提交与合并不代表真实产品效果验收。**整个阶段尚未全部验收**：个人模型凭据、本人 Chrome 安装与真人会话/盲判/持续使用仍缺。MIT 已由发起人选择并落地。Chromium fixture 自动验收已通过；它不等于真人安装或 GitHub 实际效果。状态 `verified` 表示相应工程子项经离线验证，其余子项分别列明缺口。

最新机器记录：[phase-status-2026-10-02.json](phase-status-2026-10-02.json)。阶段报告：[2026-10-02-phase-review.md](../reports/2026-10-02-phase-review.md)。远端已核对：[#10](https://github.com/victorzhong0110/gold-miner/pull/10) 在 CI 通过后合并，合并提交 `b93f89ee02841c25a9f9917345a4e5be77a9fb17`；#2–#9 已全部 closed/merged，当时没有遗留开放 PR。合并后 main 复验 243 项 Python + 45 项 Node 通过；合并状态不改变表中未完成的实际验收。

| ID | 任务 | 状态 | 本轮证据或未完成原因 |
|---|---|---|---|
| WP1-01 | 核对基线与交接 | verified | 独立工作区、唯一写入者、基线与 PR 祖先已核对 |
| WP1-02 | 对齐协议与规范 | verified | 规范入口显式对齐；历史 v0.3/v0.4 未改 |
| WP1-03 | 真实模型客户端和配置 | partial | HTTP 客户端与恢复回归已测；2026-10-05 修 S6（max_tokens 256→2048、剥离 `<think>`、探测校验内容）并加 12 项回归。个人模型实测仍缺发起人复测 |
| WP1-04 | 接通完整检索执行链 | verified | e1_pipeline.py + test_e1_pipeline.py：保留原文、语言标签、预算和字段检查 |
| WP1-05 | 冻结评估材料 | partial | 历史冻结材料已保留；正式比较须冻结具体模型与新代码 SHA |
| WP1-06 | 准备 E2/E3 正式材料 | partial | E2 会话包、E3 真实片段已保留；正式多轮材料和实际会话待补 |
| WP1-07 | 离线基线与操作说明 | verified | 统一离线套件含 E6/E8/内容脚本/源码与包一致性 |
| WP2-01 | 预先登记判断标准 | partial | protocol、judgment-guide 已有标准；正式新批次须预登记具体模型 |
| WP2-02 | 运行 E1 A/B/C/M | partial | A 组和 README 配对有历史 live 记录；B/C/M 尚未实测 |
| WP2-03 | 运行强对照 D | pending-live | 工具侧已就绪：新增 `e1_d_control.py` 录入+比较，harness 接 `--d-input`，命中/幻觉/未核实分开计数（2026-10-05）。**对照本身仍未运行**，D 是真人强对照，不能由 fixture 补齐 |
| WP2-04 | 盲判和增量分析 | partial | blind_eval.py 已实现去重、遮蔽与回填；真人盲判尚未执行 |
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
| WP3-07 | 实机验收 | partial | Chromium fixture 验收 12 项通过（2026-10-05 新增长页可见性、探测读输入框、清除陈旧绿灯）；S1/S5/S6 已按首轮真机反馈修好。个人 Chrome 安装与真人体验仍留给发起人，**S6 修复后的模型路径未在真机复测** |
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

## 2026-10-05 续作：真机问题批量修复

依据发起人 2026-10-04 首次真机操作记录的 [S1–S6 与 O1](../session-issues.md)，
本轮一次性修完 S1–S6 并逐条加回归锁定。明细与逐项回归位置见
[session-issues.md 的修复结果表](../session-issues.md#2026-10-05-批量修复结果)。

S6 是阻塞项：修复前 `max_tokens: 256` 使推理模型的预算全部消耗在 `<think>` 上，
JSON 尚未输出即 `finish_reason: "length"`，**模型路径全程未真正运行**，而选项页绿灯、
终端探测和真实请求三处都显示成功。现改为单一常量 2048、显式剥离 `<think>`、
探测校验返回内容，并让降级原因可区分（截断／空内容／响应异常／端点无效／缺授权）。

S4 的处置与原记录的建议不同，说明理由：D 组衡量的是「换一个更强、有人类在场的系统
能做到什么」，自动化它就毁掉了对照意义。因此工具不执行助手，改为**录入 + 比较**：
新增 `experiments/E1-cross-language-search/scripts/e1_d_control.py`，
harness 接受 `--d-input`，命中／幻觉／未核实三者分开计数，没记录的任务保持 owner-blocked。

验证（**均为 fixture/自动证据，不等于真人验收**）：

- `python3 scripts/run_offline_suite.py` → exit 0，**293 Python + 65 Node** 通过
  （上一轮 267 + 53；本轮新增 17 项 D 组、12 项模型输出、4 项区域错配、3 项挂载点、其余为 S1/S5/S6 回归）。
- Chromium fixture 验收 **12 项全绿**（[记录](../reports/browser-acceptance-2026-10-05.json)），
  其中 3 项本轮新增：长结果页面板无需滚动即可见、探测读输入框而非陈旧存储、改动 BYOK 清空陈旧绿灯。
- `dist/build-manifest.json` 已重建，产物与源码逐文件哈希一致。

仍然**未发生**、不得据此宣称的事：发起人真机复测（含 S6 修复后模型请求次数确实 > 0）、
真人盲判、E1 B/C/M/D 实测、E2 会话、E3 对照、O1 复测。这些仍按各自状态行记为
`partial` / `pending-human` / `pending-live`。
