# E3 现成工具翻译对照协议与观察模板（2026-09-18，对照输出未运行）

对应：`fragments-2026-09-17.md`（片段冻结，`materials_commit: 2be593765150adb15b92c2093505d48ecbcf769a`）、
`docs/plan/v0.4.md` W6 与第 5 节 E3 行、
`experiments/E1-cross-language-search/reading-baseline.md` v1、
`docs/engineering/prerequisites.md` 第 6 节“自建翻译启用时”行、
`docs/reports/w6-baseline-connectivity-2026-09-17.md`。
状态：8 条仓库内片段是 smoke / 冒烟集（只核 excerpt＋label 管道，不是真实阅读场景覆盖）；
本文件只给对照协议、源风险笔记与空观察模板；翻译对照输出未运行；零付费调用；零密钥。

将改路径（AGENTS.md 第 18 条）：本文件为新建；另改 `docs/reports/w6-baseline-connectivity-2026-09-17.md`（E3 行追记）
与 `docs/backlog.md`（W6 行）；不改 `docs/plan/v0.3.md`、仓库名、`LICENSE`、扩展代码。

## 0 诚实边界

- 片段范围：`fragments-2026-09-17.md` 的 8 条是 **smoke / 冒烟集**，只核 excerpt＋label 管道；
  不是真实多轮 issue 讨论、引用或纠错覆盖。建议继续作冒烟用。正式对照需另取真实项目的代码 / 注释 / 讨论线程，
  不得把本 8 条写成已覆盖真实阅读场景，也不得在仓库内编造伪“真实项目”片段。
- 不编造实验结果与准确率数字。本文件不含任何译文输出、不含缺口结论、不含准确率。
- 不调用付费/个人模型 API；不点 Subscribe/Go；零支出。本环境未发起任何翻译请求。
- 翻译输出列与判定列全部填“未运行”；工具版本、浏览器版本、设置、等待与费用全部记“未知”。
- 源风险笔记（第 2 节）只描述 SOURCE 原文中的极性/限制/代码/论证标记，不推断任何工具会如何翻译。
- W4 评估检索、W5 短会话、个人 API/模型探测均未发生，本文件不替代其中任何一项证据。
- 付费调用计数：0。密钥扫描：本文件无 `sk-` / `ghp_` / `github_pat_` 模式（短形式说明文字除外，无密钥值）。

## 1 对照协议（待运行，不在本文件执行）

### 1.1 工具与记录项

- 基线工具：沉浸式翻译双语对照模式（段落级双语显示），见 `reading-baseline.md` v1。
- 降级项：Chrome 内置翻译，仅在基线工具失效时启用并在行记录中标明。
- 每次对照必须记录：工具名、工具版本（或未知）、浏览器版本（或未知）、设置导出（目标语言、显示模式原文+译文/仅译文，不含密钥）、
  语言对（zh→en / en→zh）、原文是否可见（是/否/未知）、失败记录（工具失效、段落错位、超时、费用）。
- 本环境状态：工具版本未知、浏览器版本未知、设置未实测——因为未运行 live 工具。后续运行者在新日期文件中补记实测值，不得回填本文件。

### 1.2 步骤

1. 按 `fragments-2026-09-17.md` 的文件＋行定位原文（`materials_commit` 时刻内容，可用 `git show SHA:路径` 核对）。
2. 对 F-01..F-08 逐条生成译文（运行者执行，本文件不代填）。
3. 回查原文定位，逐条判定：术语是否走样、否定/限制极性是否保留、代码/标识符/链接是否受损、讨论关系是否改变。
4. 严重误译单列（原文定位＋是否改变理解＋翻译与解释是否混淆），见工程检查第 6 节。
5. 流畅度不代替忠实度；无缺口则不启动自建翻译比较（v0.4 第 7 节）。

### 1.3 离线已核验项（本文件编写时实际运行，无网络、无凭据、零费用）

- `git cat-file -e 2be5937:<5 个引用源文件>` 全部存在（`experiments/E9-glossary/terms.yaml`、
  `experiments/E1-cross-language-search/judgment-guide.md`、`README.md`、
  `docs/research/2026-09-17-translation-and-discovery.md`、`README.en.md`）。
- 引用行区间与摘录的逐字一致性由 `test_fragments.py` 覆盖（含 `git show` 冻结 blob 核对），见第 4 节测试记录。

## 2 逐片段源风险笔记（只看 SOURCE，不写译文）

约定：`源标记`为原文中肉眼可直接核对的字符/词；`风险`说明对照时要盯什么，不预判工具行为。

| 片段 | 来源定位 | 语言对 | 源标记（原文有） | 类别 | 对照风险笔记 |
|---|---|---|---|---|---|
| F-01 | `experiments/E9-glossary/terms.yaml` L3–6 | zh→en | `- id: clipboard-history`（ASCII 行）；`notes:` 中 `不等于只增大单次复制容量`；中英对照词 `剪贴板历史` / `clipboard history` | 术语、否定 | 否定陷阱在 `不等于` 三字；若极性丢失则把“相关但不同义”读成同义。术语行含连字符 id，须与正文术语区分。 |
| F-02 | `judgment-guide.md` L16 | zh→en | `未知不能算满足`（含 `不` + `不能` 双否定形态，实表一条否定规则） | 否定 | 短句无上下文可借；极性反转即判定口径反转。英文标识 `satisfied/conflict/unknown` 在同文件别处，对照时不得混入本句。 |
| F-03 | `README.md` L36 | zh→en | `自备`；`不承担`；`公共推理费用` | 限制 | 费用与责任边界句；`自备/不承担`若被软化（如译成建议口吻）即改变责任归属。 |
| F-04 | `docs/research/2026-09-17-translation-and-discovery.md` L41 | zh→en | `能…也不…` 让步转折；前后两个 `问题` 指代不同（回答问题 vs 想到问问题） | 讨论关系 | 论证关系在转折骨架上；若译成两个并列陈述则丢失“能回答≠会提问”的让步含义。 |
| F-05 | `README.en.md` L7 | en→zh | 双 `no`（`no installable extension` + `no product-effectiveness result`）+ 句末 `yet` | 否定 | 双重否定状态声明；漏掉任一 `no` 或 `yet` 即虚构产品状态。加粗标记 `**…**` 为格式，不属语义。 |
| F-06 | `README.en.md` L38 | en→zh | `does not fund`；`or`；`shared model proxy` | 限制 | 与 F-03 同一边界的英文表述；`does not` 辖域覆盖 `fund…or run…` 整段，缩小辖域即改变边界。 |
| F-07 | `README.en.md` L24–28 | en→zh | `separate decision paths`（讨论关系）；`is not a go/no-go gate`（否定+术语）；`experiments/E1-cross-language-search/queries.yaml`（代码路径）；`is not frozen`（状态否定） | 代码、术语、否定、讨论关系 | 同窗四风险：路径须逐字保留（大小写、连字符、斜杠）；`go/no-go gate` 不得直译为门；`not frozen` 为状态否定，漏 `not` 即虚构冻结。 |
| F-08 | `judgment-guide.md` L11 | zh→en | 行内代码 `` `scripts/github_search.py:canonical` ``（路径+冒号+函数名） | 代码 | 唯一纯代码行；翻译不得改写路径、函数名、冒号与反引号。周围中文标点不得侵入代码段。 |

## 3 观察模板（空表，翻译与判定均未运行）

填写规则：`translation_output`、`polarity_kept`、`limit_kept`、`code_intact`、`discussion_kept`、
`severe_mistranslation`、`notes` 在未运行时一律填 `未运行`；工具版本等未知项填 `未知`。不得填推测译文。

| frag | tool | tool_version | browser | settings | lang_pair | original_visible | translation_output | polarity_kept | limit_kept | code_intact | discussion_kept | severe_mistranslation | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-01 | 未运行 | 未知 | 未知 | 未知 | zh→en | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-02 | 未运行 | 未知 | 未知 | 未知 | zh→en | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-03 | 未运行 | 未知 | 未知 | 未知 | zh→en | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-04 | 未运行 | 未知 | 未知 | 未知 | zh→en | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-05 | 未运行 | 未知 | 未知 | 未知 | en→zh | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-06 | 未运行 | 未知 | 未知 | 未知 | en→zh | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-07 | 未运行 | 未知 | 未知 | 未知 | en→zh | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |
| F-08 | 未运行 | 未知 | 未知 | 未知 | zh→en | 未知 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 源风险见第 2 节 |

机器可读 JSONL 模板（字段名固定，值在本轮全部为 `未运行`/`未知`，不含译文）：

```jsonc
// 每片段一行，示例为字段模板而非数据：
// {"frag": "F-01", "tool": "未运行", "tool_version": "未知", "lang_pair": "zh→en",
//  "original_visible": "未知", "translation_output": "未运行", "polarity_kept": "未运行",
//  "limit_kept": "未运行", "code_intact": "未运行", "discussion_kept": "未运行",
//  "severe_mistranslation": "未运行", "notes": "源风险见第 2 节"}
```

## 4 本轮未做项与测试记录（如实记录，不是遗漏）

- 翻译对照输出：未运行（零请求、零费用；工具版本/浏览器/设置/等待未知）。
- 运行命令（实际运行）：`python3 -m unittest discover -s experiments/E3-faithful-reading -p "test_*.py"` → 通过（片段冻结 8 条、引用逐字、`materials_commit` 存在性、`git show` blob 核对均绿）。
- 种子集补齐：未做（`seed-tasks.draft.yaml` 仍 `draft-unfrozen`，`entries: []`）。
- SHA 冻结回填：未做（`queries.yaml` 的 `eval_frozen_commit`、`run-settings.json` 的 `freeze.*` 保持 `null`）。
- E8 复测：未运行（基线仍为 `2026-09-17-probe.md`）。
- W4 评估检索、W5 短会话、个人 API/模型探测：均未发生，本文件不替代其中任何一项证据。
