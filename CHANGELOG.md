# Changelog

## Unreleased — 2026-10-05 E6 probe-record schema 不可满足，已修

- `probe-record.schema.json` 的 required 有 30 个字段名，properties 只描述 16 个，
  `additionalProperties` 却是 false。那 14 个字段被**同时要求与禁止**——
  任何对象都无法满足该 schema。
- 一直没被发现的原因：`test_e6_probe.py` 的
  `assertEqual(set(record), set(schema["required"]))` 意图正确且一直通过，
  但**只比对了字段名，没有拿 schema 去过一遍记录**。
- 方向判断：工具产出 30、required 30、schema 缺描述的必填字段为 0，
  工具产出的是严格超集 → 改 schema，不削工具。
- 补齐 14 个字段声明（类型取自实测），并给 `run_id` 补 minLength 与说明。
- 测试新增两个模块级断言：`required - properties` 必须为空（无需 jsonschema）、
  用 jsonschema 真验记录（缺库时回退）。原名字比对保留。
- 验证：补声明后今日新记录与 **2026-09-22 已记录记录双双 VALID**（证明产物一直
  是对的）；重新引入原缺陷测试失败、还原通过；**全仓库 13 个 schema 现全部可满足**。
- 离线套件 362 Python + 58 Node 通过，付费请求 0；`e6_probe.py` 行为未改。

## Unreleased — 2026-10-05 盲判记录可回填为 schema 合规记录

- 三方字段集不一致：schema 要 `run_id`/`task_id`/`repo` 且禁止 `blind_id`；
  判定表与 `analyze` 用 `blind_id` 且不产那三个。**发起人按判定表填完的记录
  无法通过仓库唯一声明权威的 schema**（`additionalProperties:false` 拒绝
  `blind_id`，同时缺三个必填字段）。下游要么失败要么绕过。
- 两边形状各自合理（非盲知道 task/repo，盲判刻意只知道 blind_id），
  缺的是桥。新增 `schemas/judgments-blind.schema.json` 描述盲判输入形状，
  新增 `blind_eval.export_judgments()` 回填为 `judgments.schema.json` 形状：
  身份字段**从 blind-key.json 取**而非编造，**不写 arm**，缺 `kind`/`notes` 拒绝导出
  （不替判定人填值）。
- 三方漂移棘轮 7 项：判定表字段集必须等于盲判 schema 的 required；
  `analyze` 读取的字段都必须有描述；显式断言两套 schema 不兼容。
- **未改判定材料**——字段集现在被测试约束而非修改。
- 离线套件 362 Python + 58 Node 通过，付费请求 0。

## Unreleased — 2026-10-05 A/B/C/M 记录耗时并写出 latency_cost.jsonl

- 按 schema 校验 4 个已记录运行：1862 行 0 违规，记录形状本身健康。
  但 `latency-cost.schema.json` 存在而只有 D 组写了对应文件。
- 根因不是忘了写文件，而是**需要的数从来没被采集**：`e1_pipeline` 写文件前
  只有整轮 `started_at`/`finished_at`，全文件无 `time.monotonic()`；
  模型生成与逐题检索两半都未计时。造文件只能填 0，比不写更糟。
- 影响：协议第 6 节「成本与等待」的「耗时」这一半在任何记录里都不存在，
  与 WP4-07 长期 `partial` 的理由一致。
- 已修：`e1_batch.run_batch` 在正常/`except`/取消三路径写回 `elapsed_ms`；
  `e1_pipeline` 对 `generate()` 计时并按 (task, arm) 累积；
  新增 `latency_cost_rows()` 并写出 `latency_cost.jsonl`（空也写）。
  **`visible_cost` 一律不编造**：live 写 `unknown`、fixture 写
  `fixture-no-model-calls`。
- **未回填历史运行**：旧运行耗时从未被测量，补全 0 文件等于宣称当时耗时为零。
- `test_e1_pipeline.py` 17 → 24 项，含用真 sleep 的 stub 断言 `elapsed_ms > 0`。
- 离线套件 354 Python + 58 Node 通过，付费请求 0。

## Unreleased — 2026-10-05 判定分析补上协议要求的 B→C

- 协议第 6 节要求三个比较（A→C / M→C / **B→C 判断复杂程度是否值得**），
  `blind_eval.analyze` 只产出前两个，**`c_minus_b` 缺失**——而这正是「这套复杂度
  值不值得」的产品决策。B 的 suitable 早已算出，只是没参与差集。
- 修前总开关只看 A/C/M，**不看 B**：B 组判定全缺失时 A→C、M→C 仍标 `complete`，
  给出没兑现的保证。改为**每个比较项各自带完整性**，不完整写
  `{'status':'incomplete-no-comparison','needs':[...]}`，绝不写空列表
  （空列表会被读成「这组没有独有合适候选」，那是结论）。
- B 缺失只影响 B→C，不连累 A→C/M→C。**D 刻意不做差集**：它走联网助手、
  请求机制、输出预算和时间不同；本次 D 实跑同批20题，不是子集；
  D 的逐任务集合仍可见，另加 `d_not_differenced` 说明。
- 用已记录运行的真实任务状态核对：两次失败吃掉比较项，**20 题里 2 题至少
  有一项因运行失败不可得**，18 题运行结构允许三项比较（结构判断，非效果结论）。
- `test_blind_eval.py` 15 → 19 项；离线套件 347 Python + 58 Node，付费请求 0。

## Reverted — 2026-10-05 B 组查询长度的三条推断

同日提交过的「B 组查询与 GitHub 关键词检索结构性不匹配／C−B 被长度污染／
B 是稻草人」**已被实跑数据否证，现撤回**。否证数据：B 跨题去重 156 个仓库
（A 为 51），`B − A = 106`；11/20 题的 B 译句查询返回 ≥1 条。
根因是探针把整句按词边界截断，**同时改变了长度与语义完整性**，
测到的 0–1 条是「半句话检索不到」。唯一仍成立：193 字符那条可复现 422（1/20 题）。
教训：当探针本身改变了被测对象，差异不能归因于你正在操纵的那个变量。
详见 [完整自我推翻记录](docs/reports/2026-10-05-b-arm-query-length-confound.md)。

## Unreleased — 2026-10-05 A/B/C/M 运行写 failures.jsonl

- D 组运行写 `failures.jsonl`，A/B/C/M 不写，而 `schemas/failures.schema.json`
  定义了该文件——同一实验的两类记录形状不同，消费方需特判。
- `e1_pipeline` 早已检测失败并据此返回 exit 2（`:194`），却只交给退出码、不落盘。
  新增 `failure_rows(result)` 并在 `main()` 写出账本：字段全部取自已有的
  `generation_records` 与 per-task `status`/`errors`/`reason`，不编造；
  遵守 `additionalProperties: false`；空也写文件（缺文件与「没失败」无法区分）。
- **未回填历史运行**：三次历史运行当时没产生该文件，事后补等于伪造记录。
- 顺带记录但不改：`:194` 判定失败不含 `tasks_partial`，
  只有 partial 而 `failed_requests` 为 0 时会 exit 0 却有账本行，口径不一致，
  是否让 partial 也算失败属发起人决定。
- 离线套件 343 Python + 58 Node 通过，付费请求 0。

## Unreleased — 2026-10-05 提示词与 pipeline 查询规则矛盾

- 查实一条已记录但未处理的矛盾：`prompts/c-rewrite.txt:13` 许可
  `in:description` 与 `stars`，而 `e1_pipeline.py:31-32` 对 `in:`/`stars:` 等
  一律 `ValueError`。模型照提示词做才是错的，失败却会记成模型错误。
  三组中仅 C 许可；M 未提 `in:description`/`repo:`/`user:`/`org:`；B 已全面禁止。
- prompts 属冻结材料，修复应落 `eval.batch_2`，本轮不改，只加防再犯检查：
  `e1_materials_check.py` + `test_e1_materials_check.py`（10 项），
  `materials-status.json` 以 `file:line` + 原文引用记录，测试断言引用未变。
- 规则从 `e1_pipeline.forbidden_query_syntax` 读取，不在检查器里复刻。
- **推翻重写了自己第一版检查器**：它从中文散文猜意图，把 C 的「本步不要写
  in:readme」和 M 的「不准加…stars:」都判成允许。新版只报告「是否提到」，
  意图判断改由人工记录 + 引用 + 棘轮测试承担。
- 离线套件 336 Python + 58 Node 通过，付费请求 0。

## Unreleased — 2026-10-05 盲判材料遮蔽强度实测与私密 salt 机制

- 实测 `evaluation/2026-10-04-minimax/` 的遮蔽强度：233 个 blind_id 中
  **196 个（84%）可确定归属单一组**，A 组基线 4/4 全部暴露。根因是
  `blind_id = sha256(run_id + ':' + task_id + ':' + repo)` 不含 arm，
  公开运行记录即可重算分组，不需要打开 `blind-key.json`。
- 新增 `blind_eval.py --audit-masking`：让工具自报遮蔽强度，不读 key、不写判定材料。
- 新增私密 salt 支持（`E1_BLIND_SALT` / `--salt-file` / `--key-out`）。
  salt 不走 argv 以免进 `ps` 与 shell 历史；空白 salt 视为「没有」而非弱 salt。
  salt 只改变 ID；公开 task_id/repo 仍可匹配原始运行。审查已修复原工具错误的“加盐后0可还原”结论：身份匹配仍是233/233，单组归属196/233。
- 成功零候选组初始化为完整空集，blocked/partial 仍阻断相关比较。旧“仅7题三项比较可用”已撤销；按实际运行状态为18题，真人判断仍未完成。
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
