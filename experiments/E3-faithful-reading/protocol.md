# E3 忠实阅读检查协议（W6，2026-09-22）

本文件是本包自己的协议。E1 协议第 7 节仍有效：不用中文 README 占比取消某一方向，不用小样本百分比宣布产品成功，不在本包决定搜索或推荐的继续、缩小或暂停。那些决定属于 W8，本包不写。

对应：`docs/plan/v0.4.md` 第 5 节 E3 行、`reading-baseline.md` v1、`docs/engineering/prerequisites.md` 第 6 节。旧的 8 条仓库内片段仍是冒烟集，见 `fragments-2026-09-17.md`，本协议不把它们改成真实阅读覆盖。

## 将改或新增的路径

- `experiments/E3-faithful-reading/protocol.md`
- `experiments/E3-faithful-reading/e3_check.py`
- `experiments/E3-faithful-reading/test_e3_check.py`
- `experiments/E3-faithful-reading/schemas/observation.schema.json`
- `experiments/E3-faithful-reading/runs/2026-09-22-w6/`
- `experiments/E6-api-probe/protocol.md`
- `experiments/E6-api-probe/e6_probe.py`
- `experiments/E6-api-probe/test_e6_probe.py`
- `experiments/E6-api-probe/schemas/probe-record.schema.json`
- `experiments/E6-api-probe/runs/2026-09-22-w6/`

不改 `docs/backlog.md`、`README.md`、`README.en.md`、`docs/plan/v0.3.md`、`docs/plan/v0.4.md`、`experiments/E1-cross-language-search/`、`experiments/E2-open-ended-discovery/`。

## 问什么

现成翻译在少量公开片段上，会不会改掉术语、否定、限制、代码或讨论关系。流畅度不代替忠实度。没有实际缺口就不比较自建翻译。本包即使看到缺口，也不实现整仓库翻译，也不启动自建译文比较。

## 片段

运行前固定 6 条，见 `runs/2026-09-22-w6/fragments.jsonl`。两方向都有。类别覆盖术语、否定、限制、代码、讨论关系。材料来自当时可打开的公开 README 与 issue 评论，并记下仓库 SHA 或评论正文哈希。数量固定，不在看到译文后追加或删改原文。

## 工具

- 阅读基线仍是沉浸式翻译双语对照。本环境没有该扩展，基线记未运行。
- Chrome 内置翻译界面本次没有在 GitHub 页面上操作，记未运行。
- 实际调用的是 Google Translate 公开接口 `translate.googleapis.com/translate_a/single`，参数 `client=gtx`。工具版本未知。这是降级探测，不能写成沉浸式翻译或 Chrome 界面已经测过。

## 记录

候选片段、译文、判定各自一行 JSONL，再合并为 observations。

判定字段：`terminology_kept`、`polarity_kept`、`limit_kept`、`code_intact`、`discussion_kept` 取 `yes` / `no` / `不适用` / `未运行`。`severe_mistranslation` 与 `changes_understanding` 取 `yes` / `no` / `未运行`。

无译文时，上述字段和 `error_location` 只能是未运行，不能写缺口。有缺口时 `error_location` 引用译文中的走样位置。`code_intact=yes` 时，片段里的 `must_keep` 必须原样出现在译文中。

严重误译指改变理解，不只是别扭。判定者身份写入 `judge`。本批技术核对不是语言使用者体验。

## 不能声称的事

这 6 条上的计数只描述这 6 条和这次工具，不是准确率，也不是“现成翻译足够”或“必须自建”的已决定结论。
