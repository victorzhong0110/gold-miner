# Changelog

## Unreleased — 2026-10-05 真机问题批量修复（发起人首轮真实操作反馈）

修完 `docs/session-issues.md` 的 S1–S6。**不构成 E1/E2/E3 任何效果证据**，
模型路径在发起人复测前仍算未验证。

- **S6 ★阻塞项**：`max_tokens` 256 → 2048（`shared.js` 单一常量，扩展与终端探测共用）。
  原值让推理模型把预算全花在 `<think>` 上，JSON 未输出即 `finish_reason: "length"`，
  模型路径全程未真正运行，而三处探测都显示成功。新增 `stripReasoning` / `readModelChoice`，
  显式剥离思考内容；降级原因可区分截断／空内容／响应异常／端点无效／缺授权，不再一律报「模型不可用」。
- **S1 假成功绿灯**：探测改读输入框当前值而非 `chrome.storage.local`；改动任一 BYOK 字段
  即清空状态栏；结果带实际被测主机。区域错配的裸 401 直接提示换主机而不是让人重填 key。
- **S5 面板落在长页面底部**：改为插到内容容器顶部（原来追加到末尾，36 条结果时需滚到页面最底部
  才出现，等同于功能不存在）；无锚点时固定定位悬浮，不再静默追加到 body。
- **S2/S3 区域与主机**：`byok.example.env` 默认改用官方文档有列的主机并标注三个主机的区域；
  401/403 在区域主机上归类为 `wrong_region`（业务码 1004 同理），记录带 `host_region` 与处置建议。
- **S4 D 组强对照**：不再是 stub。新增 `e1_d_control.py` 做真人记录的**录入 + 比较**，
  harness 接 `--d-input`。D 衡量「换更强、有人类在场的系统能做到什么」，自动化会毁掉对照意义，
  故工具不执行助手。命中／幻觉／未核实三者分开计数，未记录任务保持 owner-blocked。
- 离线套件 293 Python + 65 Node 通过；Chromium fixture 验收 12 项全绿（新增 3 项）。

## 0.1.0-trial — review follow-up (Draft PR #2)

- 存储隔离改为 `chrome.storage.local.setAccessLevel`；失败则拒存密钥。
- 可注入模型客户端；`hasModel` / `processing_mode=model` 仅在模型路径真正跑过时设置。
- 搜索失败不再写入成功缓存；缓存存排序前候选，展示时再套用反馈/个性化。
- Explore 用仓库 topics/描述构造相关查询；导出/导入可回放 SEARCH/EXPLORE 缓存。
- 离线补 service worker 消息流测试。真机加载仍 **未运行**。不声称 WP1–6 完成。

## 0.1.0-trial — 2026-09-19

- WP1：协议冲突清理（扩展闸门、stars 下限、字段节号）、CI、BYOK 探测骨架、B/C/M 可审计查询生成、E1 评估/开发分离确认、已核对种子、E3 真实片段、E2 会话包。
- WP2：E1 fixture harness、盲判模板、他语言空间 vs 更多搜索分析脚本、E3 现成翻译清单、首轮决策模板（live 格 owner-blocked）。
- WP3–WP4：可本地加载的 MV3 试验扩展（设置、搜索/探索、反馈、状态、SPA、规则排序、缓存、预算、导出清洗）。
- WP5：双语 README、上手/配置、反馈 issue 模板、缓存导入导出脚手架。
- WP6：干跑清单、已知限制、许可证草案、本版本号。

未包含：真实 E1 评估运行、E2 会话、发起人模型探测、Chrome 商店、已决定 LICENSE。
