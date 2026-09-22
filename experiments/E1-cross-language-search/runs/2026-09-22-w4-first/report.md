# W4 E1 首轮报告（2026-09-22）

对应 `docs/backlog.md` W4、`w4-run-instructions.md`、协议第 4–7 节与第 9 节。
运行目录：`runs/2026-09-22-w4-first/`。材料提交 `6010be0eee6d0e7f46ad851931741b81f741e0f0`。
这是一次真实检索和代理技术核对，不是产品取舍，也不是总体召回。

## 1 做了什么

- 开放题 `eval.batch_1` 的 A 组：20 条原查询，默认仓库搜索，每条 1 次，无令牌，间隔 7 秒。20 次都返回了 HTTP 成功。
- B/C/M：未验证词表机械匹配后 20 条全部 blocked，请求数 0。没有补造查询。
- D：未运行。没有联网助手会话。
- E9：未展开。没有可比较的 B/C/M 结果。
- 已知目标 8 条只跑了 A 组。7 次成功，1 次失败。
- 有候选的任务核对了合并结果的前 5。判定人 `agent:bc-74855d06-e3bc-5479-9555-dd499ba84e4f`。`novel_to_judge` 与 `worth_following` 都是 `unknown`。

时间：2026-09-22T01:43:35Z 至 2026-09-22T01:46:51Z。`github_token_used` 为 false。模型请求 0。可见费用：GitHub 公开接口无令牌，模型费用 0；人类核对分钟数未知。

## 2 成本

| 项 | 数值 |
|---|---|
| 开放题 A 组 GitHub 请求 | 尝试 20，成功 20，失败 0 |
| 开放题 B/C/M | 尝试 0，blocked 各 20 |
| 种子 A 组 | 尝试 8，成功 7，失败 1 |
| 模型请求 | 0 |
| 合并候选行 | 100（开放题 68，种子 32） |

失败的那次是 `seed-zh2en-02`，错误文本为 `HTTP Error 403: rate limit exceeded`。这里不另写剩余额度。

## 3 开放题：两方向

下面只统计 A 组前 5 里、用途 `yes` 且硬条件 `satisfied` 的仓库。硬条件 `unknown` 的单列，不算满足。使用者愿意继续看：未运行。

中文找英文项目（zh2en）：

- `zh2en-eval-01` 局域网互传：`Maidehua/LanDrop`、`chengcheng84/rustysend`、`Hisakazu333/NekoDrop`、`13429837441/localShare`。`LumiaGG/TransportFile` 用途符合，但 README 没有写清局域网，硬条件未知。
- `zh2en-eval-05` 鼠标手势：`ron159/iGestures`、`Inonvation/cad-gesture`、`decajoin/mouse-gestures`、`ubuchow/MouseGesture`。`szboboxing/mouse-gesture-actions` 只部分符合。
- `zh2en-eval-06`：1 条候选，Composer 安装插件，部分符合。
- `zh2en-eval-03`、`zh2en-eval-04`、`zh2en-eval-10`：前 5 用途不符合。多条中文查询的前排重复出现 `cirosantilli/china-dictatorship` 及其近似仓库，以及 `gege-circle/.github`。这是这几条结果里看到的现象，不是全站索引结论。
- 合并后 0 条，因此没有前 5 可核对：`zh2en-eval-02`、`zh2en-eval-07`、`zh2en-eval-08`、`zh2en-eval-09`。0 条不等于这类项目不存在。

英文查询（en2zh）：

- `en2zh-eval-01`：`FinchipAIOrg/housing-fund-loan-calculator` 用途符合且硬条件满足。`v0v0/income-tax-calculator` 是税后工资计算，只部分涉及公积金。
- `en2zh-eval-05`：`magician000/DingTalkRobot-python` 用途符合。`zangjiahe/DingTalkRobot` 描述像钉钉机器人，README 404，硬条件未知。
- 合并后 0 条：`en2zh-eval-02`、`en2zh-eval-03`、`en2zh-eval-04`、`en2zh-eval-06`、`en2zh-eval-07`、`en2zh-eval-08`、`en2zh-eval-09`、`en2zh-eval-10`。

有价值的新发现：未运行。判定人不是人类使用者，新颖性和是否继续看都是 unknown。

## 4 已知目标命中@30

只针对 A 组、合并后前 30。不是召回率。查询是从来源短句反推的，盲测未完成。

成功的 7 条里，指定仓库进入前 30 的是 0。失败的 `seed-zh2en-02` 不计入这 0/7，因为请求没有返回结果。

- zh2en：成功 3 条均为未命中；另 1 条 403。
- en2zh：4 条成功，均为未命中。

## 5 不可归因

B、C、M 没有发出检索。不能比较简单译词、跨语言扩展和同语言扩展，也不能把 A 组里的技术符合说成跨语言增益。字段只有默认字段。README 配对诊断未做。D 未运行。

协议第 7 节的继续、缩小或暂停：本批证据不够，不在这里写成已决定。

## 6 漏掉的好结果

种子目标 7 个都没有出现在 A 组前 30，说明这 7 条反推查询的原生搜索没有把指定仓库带进窗口。不由此推断别的查询也找不到它们。开放题里 0 条结果的任务，没有候选可标成漏掉的好仓库。

## 7 下一工作包

W5 的会话设置已经在仓库里，仍然需要发起人短会话。本报告不替代那场会话。
