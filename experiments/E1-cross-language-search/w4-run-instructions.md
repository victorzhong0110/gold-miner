# W4 运行说明（首次运行前）

对应 `docs/backlog.md` W4、`docs/plan/v0.4.md` W4、E1 协议第 2–7 节。
本文件是运行说明，不是效果结论。模型端点仍见 `docs/decisions/0002-model-endpoint-config.md`，这里不把它写成已验证。

## 1 本批固定了什么

- 开放题：`queries.yaml` 的 `eval.batch_1`（20 条）。文件里的 `eval_frozen_commit` 等四个指针保持 `null`，避免文件包含自身提交 SHA。已存在的提交 SHA 写在后续的 `run-settings.json` `freeze` 字段和运行清单里。
- 提示词：`prompts/` 保持原文，本批不调用它们。
- 词表：`experiments/E9-glossary/terms.yaml` 仍是未验证候选。变体文件 `variants/eval-batch-1-glossary.json` 只做机械匹配。
- 种子：`seed-set.jsonl` 共 8 条。来源有两处：HelloGitHub 第 99 期，以及 awesome-cli-apps 主题清单。其中有 stars 低于 100 的低热度条目。stars 与 README 语言是冻结当时的 GET 记录，见每行 `bias_note`。
- 预算与字段：沿用 `run-settings.json` 里已有的 A/B/C/M 预算和默认字段。README 配对诊断本批不做。
- 模型标识：`concrete_model_id` 仍为 null。本批模型请求数为 0。

## 2 词表路径为什么几乎不发出查询

`scripts/e1_glossary_variants.py` 的规则：

- 只有原查询完整落在某一个词条的源语言短语里，才为 B/C/M 生成变体。
- 原查询还剩否定、工具名或其他词时，不删掉这些词来凑翻译，该任务 B/C/M 记为 blocked。
- 两个词条最长匹配并列时记为 blocked，不选边。
- 没有匹配记为 blocked。
- 不调用模型，不手写词表以外的查询。

对当前 `eval.batch_1`，这会让 B/C/M 全部 blocked。这是覆盖结果，不是同义结论。D 组联网助手未运行。E9 三组比较未展开，因为没有可解释的 C 对 B 或 C 对 M 增益。

## 3 怎样跑

单元测试（无网络）：

```text
python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"
```

评估检索只在 `run-settings.json` 的四个冻结指针都指向已存在提交之后进行。指针为空时 `e1_w4_run.run_eval_arms` 拒绝运行。

实时检索使用环境变量 `GITHUB_TOKEN`（可空）。不把令牌写入仓库。无令牌时按公开额度串行，请求间隔用 7 秒，失败原样记入 manifest，不补候选。

已知目标只跑 A 组（每条种子 1 次搜索），看指定仓库是否进入合并后的前 30。这不是总体召回。

## 4 判定

各组前 5 做内容核对。`novel_to_judge` 允许 `unknown`。代理判定把使用者是否愿意继续看记为 `unknown`，技术判断写在 `reason`。不写盲测完成。

## 5 本包不决定的事

协议第 7 节的继续、缩小、暂停留在证据足够时再写。本批若只有 A 组检索而 B/C/M 被词表规则挡住，跨语言增益标为不可归因，不写成产品取舍。项目名称、许可证、模型供应商仍是待决事项。
