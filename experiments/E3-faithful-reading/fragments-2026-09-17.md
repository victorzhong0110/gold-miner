# E3 忠实阅读：公开片段固定清单（2026-09-17，未做翻译对照）

对应：`docs/plan/v0.4.md` W6 与第 5 节 E3 行、`docs/reports/w6-baseline-connectivity-2026-09-17.md` 第 4 节、
`docs/reports/w8-first-round-decision-2026-09-17.md` 第 3 节第 4 项、
`experiments/E1-cross-language-search/reading-baseline.md` v1。
状态：8 条仓库内片段是 **smoke / 冒烟集**（只核 excerpt＋label 管道）；
不是真实阅读场景覆盖；翻译对照未运行；零付费调用；零密钥。

## 0 固定说明

- 范围（smoke / 冒烟 only）：本文件 8 条全部取自本仓库已提交的公开文件，是 **冒烟集**，
  只用来核对 excerpt＋label 管道（文件 / 行 / 引用 / 类别字段能否被测试读出并与源文件逐字对齐）。
  它们 **不是** 真实多轮 issue 讨论、引用链或纠错场景的覆盖，也不得写成“已具备真实阅读场景覆盖”。
- 建议：继续把这 8 条留作冒烟，不要扩写成伪“真实项目”片段。正式对照集需要以后另取真实项目的
  代码、注释与讨论线程；本文件不编造这类片段。
- 本文件只固定“读什么、在哪里、为什么选它”，不包含任何翻译输出、缺口结论或准确率数字。
- 片段全部取自本仓库已提交的公开文件（下述 `materials_commit` 时刻的内容），无需网络、无需凭据即可核对。
- 翻译对照（现成工具 vs 原文）未运行：未调用沉浸式翻译、Chrome 内置翻译或任何模型；工具版本号实测、等待与费用记录均为未知。
- 阅读基线沿用 `reading-baseline.md` v1（沉浸式翻译双语对照模式为基线、Chrome 内置翻译为降级项）；本文件不改变该基线。
- `materials_commit: 2be593765150adb15b92c2093505d48ecbcf769a`（创建时 `git rev-parse HEAD` 实测，非编造；仅标识片段出处提交，不构成 eval 冻结）。
- 冻结语义：本 SHA 为片段出处冻结，创建后故意不再跟随 HEAD；校验以 `git cat-file -e` 存在性加 `git show SHA:路径` 逐字核对为准。引用源文件有改动时另起新日期文件，不得直接改本文件 SHA 或引用行。
- 付费调用计数：0。密钥扫描：本文件无 `sk-` / `ghp_` / `github_pat_` 模式（见测试）。

## 1 片段（共 8 条冒烟条目，两方向 × 术语/否定/限制/代码/讨论关系）

约定：`行`为 1 起始闭区间；`引用`为该行区间内的原文摘录（标点含在内），测试逐字核对。

### F-01（zh 来源；术语＋否定陷阱）

- 文件：`experiments/E9-glossary/terms.yaml`
- 行：3–6
- 语言：zh（含 en 对照词）
- 类别：术语、否定
- 引用：
  - `- id: clipboard-history`
  - `notes: 剪贴板历史指保留多次复制记录以便回查粘贴，不等于只增大单次复制容量`
- 入选理由：术语映射（剪贴板历史 ↔ clipboard history）附带“相关但不是同义”的否定陷阱（`不等于…`），译文若丢掉否定即改变理解。

### F-02（zh 来源；否定规则）

- 文件：`experiments/E1-cross-language-search/judgment-guide.md`
- 行：16
- 语言：zh（含判定值英文标识）
- 类别：否定
- 引用：
  - `未知不能算满足`
- 入选理由：短否定规则句；翻译必须保留否定极性，否则判定口径被反转。

### F-03（zh 来源；限制/费用边界）

- 文件：`README.md`
- 行：36
- 语言：zh
- 类别：限制
- 引用：
  - `模型调用由使用者自备 API，项目不承担公共推理费用`
- 入选理由：费用与责任边界声明；“自备/不承担”类限制是 E3 要求覆盖的限制类典型。

### F-04（zh 来源；讨论关系推理）

- 文件：`docs/research/2026-09-17-translation-and-discovery.md`
- 行：41
- 语言：zh
- 类别：讨论关系
- 引用：
  - `通用 AI 能回答一个问题，也不代表用户一定会想到问那个问题`
- 入选理由：让步转折长句（能…也不…），考验译文是否保留论证关系而非只翻顺字面。

### F-05（en 来源；状态否定）

- 文件：`README.en.md`
- 行：7
- 语言：en
- 类别：否定
- 引用：
  - `There is no installable extension and no product-effectiveness result yet`
- 入选理由：双重否定状态声明；漏译任一 `no` 即虚构产品状态，是必须盯死的忠实度点。

### F-06（en 来源；限制/费用边界）

- 文件：`README.en.md`
- 行：38
- 语言：en
- 类别：限制
- 引用：
  - `the project does not fund public inference or run a shared model proxy`
- 入选理由：与 F-03 同一边界的英文表述；双向对照可检查限制语在两个方向是否都被保留。

### F-07（en 来源；代码标识＋术语＋讨论关系）

- 文件：`README.en.md`
- 行：24–28
- 语言：en（含仓库路径代码标识）
- 类别：代码、术语、否定、讨论关系
- 引用：
  - `Search and open-ended discovery have separate decision paths`
  - `The proportion of Chinese-only READMEs is not a go/no-go gate`
  - `experiments/E1-cross-language-search/queries.yaml`
  - `evaluation is not frozen`
- 入选理由：先给分路径决策理由（讨论关系），再用否定句排除伪门槛（术语 `go/no-go gate`＋否定）；
  同窗出现行内代码路径（大小写、连字符须逐字保留）与 `not frozen` 状态否定。

### F-08（zh 来源；行内代码）

- 文件：`experiments/E1-cross-language-search/judgment-guide.md`
- 行：11
- 语言：zh（含行内代码）
- 类别：代码
- 引用：
  - `` `scripts/github_search.py:canonical` ``
- 入选理由：行内代码标识；翻译不得改写路径、函数名或标点（工程检查第 6 节“自建翻译启用时”风险项）。

## 2 覆盖自查

| 方向 | 术语 | 否定 | 限制 | 代码 | 讨论关系 |
|---|---|---|---|---|---|
| zh 来源（→en） | F-01 | F-01、F-02 | F-03 | F-08 | F-04 |
| en 来源（→zh） | F-07 | F-05、F-07 | F-06 | F-07 | F-07 |

两方向、五类在冒烟集内均有条目；这只是管道自查，**不是**真实阅读场景覆盖。
数量固定为 8，不再追加（正式对照集另起新文件，取真实项目材料，不在此编造）。

## 3 对照方法（待运行，不在本文件执行）

1. 对每条片段，用基线工具（沉浸式翻译双语对照模式）生成译文，记录工具版本、浏览器版本、设置导出（不含密钥）。
2. 回查原文定位（本文件的文件＋行），逐条判定：术语是否走样、否定/限制是否保留、代码/标识符/链接是否受损、讨论关系是否改变。
3. 严重误译单列（原文定位＋是否改变理解＋翻译与解释是否混淆），见工程检查第 6 节。
4. 流畅度不代替忠实度；无缺口则不启动自建翻译比较（v0.4 第 7 节）。

## 4 本轮未做项（如实记录，不是遗漏）

- 翻译对照：未运行（零请求、零费用、工具版本未知）。
- 种子集补齐：未做。`seed-tasks.draft.yaml` 仍为 `draft-unfrozen` 且 `entries: []`。
  补齐需逐条核验 `repo/stars/readme_lang`（schema 要求 `stars >= 50`），依赖 `GET /repos` 类核心配额；
  本轮实测 `2026-09-17T21:43:33Z` 核心配额 `remaining 0/60`（共享出口耗尽），无法诚实核验，故不动种子文件。
- SHA 冻结回填：未做。`queries.yaml` 的 `eval_frozen_commit`、`run-settings.json` 的 `freeze.*` 保持 `null`。
  冻结要求种子集、提示词、预算、模型标识同时就绪（协议第 2 节），种子与模型均未就绪，回填即虚假冻结。
- E8 复测：未运行。同次实测搜索配额虽为 `remaining 10/10`，但 E8 需先读 `GET /repos` 元数据（核心配额为 0，
  复测即 403），按工程检查第 1 节“遇限流即停止”，本次不发起任何 E8 查询；基线仍为 `2026-09-17-probe.md`。
- W4 评估检索、W5 短会话、个人 API/模型探测：均未发生，本文件不替代其中任何一项证据。
