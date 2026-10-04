# Changelog

## Unreleased — 2026-10-05 盲判材料遮蔽强度实测与私密 salt 机制

- 实测 `evaluation/2026-10-04-minimax/` 的遮蔽强度：233 个 blind_id 中
  **196 个（84%）可确定归属单一组**，A 组基线 4/4 全部暴露。根因是
  `blind_id = sha256(run_id + ':' + task_id + ':' + repo)` 不含 arm，
  公开运行记录即可重算分组，不需要打开 `blind-key.json`。
- 新增 `blind_eval.py --audit-masking`：让工具自报遮蔽强度，不读 key、不写判定材料。
- 新增私密 salt 支持（`E1_BLIND_SALT` / `--salt-file` / `--key-out`）。
  salt 不走 argv 以免进 `ps` 与 shell 历史；空白 salt 视为「没有」而非弱 salt。
  实测加 salt 后仅凭公开数据可确定归属 196 → 0。**脚本不生成也不存盐**——
  写死字符串等于公开，安全剧场。
- 修正材料 README 披露：原写「映射在同一仓库」把问题说轻了，实际是跑一条命令
  即可还原 84%。salt 挡不住主动翻 key 的人，判定前仍须披露已见信息。
- 审计过程中自查出并修正一处自身缺陷：审计最初把 salt 传给了「攻击者」的重算，
  导致加 salt 后仍报 196 可还原。威胁模型应是「持有公开数据但没有 salt 的人」。
- 离线套件 326 Python + 58 Node 通过，付费请求 0。

## Unreleased — 2026-10-05 B/C/M 模型失败证据补齐

- 失败时保存脱敏、限长的模型原文（与 D 组 `e1_d_assistant.py` 已有做法一致），
  此前 B/C/M 路径把原文丢掉，`en2zh-eval-03` C 组的失败原因至今不可知。
  不改变解析行为，不影响已完成运行；成功路径不写这些字段。
- 修掉 `_extract_json_object` 的 `find("{")`/`rfind("}")` 取法：模型同时给出
  示例与答案时，示例内容会被当成真实查询记进候选集且不留痕迹。
  改为数顶层平衡括号组，多于一个即拒绝并报 `ambiguous_model_output`。
- 新增 `scripts/secret_scrub.py` 供新记录写入方脱敏；
  `e1_d_assistant.py` 故意不动（其输出已落盘并经 PR15 审查）。
- 已审计两个已完成运行，**未发现污染，既有结论不变**。
- 离线套件 316 Python + 58 Node 通过，付费请求 0。

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
