# W6 现成翻译基线与模型连接检查（2026-09-17，部分运行、部分未运行）

对应：`docs/backlog.md` W6、`docs/plan/v0.4.md` W6 与第 5 节 E3/E6 行、`docs/decisions/0002-model-endpoint-config.md`、`docs/engineering/prerequisites.md` 第 2 节。
原则：只用公开片段与免费本地检查；不启用计费、不做付费调用、不用凭据、不记录密钥。

## 1 做了什么

- 基线冒烟（本地、免费、无网络）：用既有 `readme_lang.classify`（h0-lang-v1，对 `root_files` 含英文副本的仓库判双语）对本仓库公开 README 做分类演示，确认工具链可运行。输出见第 2 节。这只是分类器冒烟，不是 E3 阅读缺口结论。
- E3 缺口定位：未运行。E3 要求“先找现成翻译的实际缺口”（术语、否定、限制、代码、讨论关系），需先固定少量公开片段（覆盖两方向与主要格式）再对照；本轮未固定片段集，未做翻译对照。
- 模型连接：未运行。`env` 检查 `GITHUB_TOKEN`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 全部未设置；按 0002“没有本地个人配置时单独标为待运行”，本次未发起任何模型请求（含最小连接探测），无费用、无等待记录。
- 密钥卫生：本文件及本次检查命令均不含密钥；脚本统一走环境变量（见 AGENTS.md 第 22–23 条）。

## 2 证据在哪里

- 本地冒烟命令（实际运行）：
  `python3 -c "from readme_lang import classify..."` 对 `README.md`、`README.en.md`、`experiments/E9-glossary/README.md` 分类。
- 实际输出（原样，未编造）：
  - `README.md -> {version h0-lang-v1, cjk_ratio 0.5518, label bilingual, has_en_readme_copy True}`
  - `README.en.md -> {version h0-lang-v1, cjk_ratio 0.0042, label bilingual, has_en_readme_copy True}`
  - `experiments/E9-glossary/README.md -> {version h0-lang-v1, cjk_ratio 0.7688, label bilingual, has_en_readme_copy True}`
  - 方法说明：三次调用传入的 `root_files` 均为 `["README.md", "README.en.md"]`，故 `has_en_readme_copy True` 迫使 `bilingual`；该标签反映的是“仓库含英文副本”而非单文件语言比例，正式 E3 片段检查须按单文件实际 `root_files` 逐条判定，不得引用本冒烟标签作阅读结论。
- 环境检查：`GITHUB_TOKEN_set False, OPENAI_API_KEY_set False, OPENAI_BASE_URL_set False, OPENAI_MODEL_set False`。
- 单元测试：`python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"` → 80 tests OK（含 W3 runner 10 项）。

## 3 失败或未知是什么

- 失败：无（未发起的调用不计失败；本地冒烟全部通过）。
- 未知：
  - 现成翻译（沉浸式翻译双语对照、Chrome 内置翻译）在 GitHub README/讨论/代码语境下的实际缺口：未知。需固定片段集后对照，流畅度不代替忠实度。
  - 模型端点、协议、模型、套餐适用范围、余额、延迟、用量：全部未知。未知余额显示未知，不推断套餐能力（见 0002）。
  - 已发送请求可能已计费：本轮零请求，零费用。

## 4 下一工作包是否具备输入

- W3 模型侧：不具备（需本地个人配置后的最小连接探测，见 0002 第 3 节；探测须记录模型、返回标识、格式、延迟、用量与错误分类）。
- W7/W8：具备阅读与费用边界输入——截至本轮，付费调用为零；任何搜索/推荐/翻译投入决策必须以“零公共补贴、使用者自备 API”为约束。
- E3 进入对照的条件：固定公开片段集（含两方向、术语/否定/限制/代码/讨论关系）并记录工具版本与设置；当前未满足。

## 5 追记 2026-09-18（E3 片段冻结与对照协议，不改上文本轮记录）

- 片段集已固定：`experiments/E3-faithful-reading/fragments-2026-09-17.md`（`materials_commit: 2be5937`，8 条 F-01..F-08，
  来源存在性与引用逐字由 `test_fragments.py` 覆盖并通过）。
- 对照协议与空模板已新增：`experiments/E3-faithful-reading/translation-contrast-2026-09-18.md`
 （含工具/版本/设置/语言对/原文可见/失败记录协议、逐片段源风险笔记、翻译与判定全 `未运行` 的观察模板）。
- Live 对照输出仍未运行：工具版本、浏览器版本、设置、等待与费用未知；零请求、零费用；未点 Subscribe/Go。
- 模型连接仍未运行（本地无个人配置）；W4/W5 仍未发生，本追记不替代其中任何一项证据。
