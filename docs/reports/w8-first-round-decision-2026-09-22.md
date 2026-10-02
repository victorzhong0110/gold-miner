# W8 首轮继续 / 缩小 / 暂停报告（2026-09-22）

对应：`docs/backlog.md` W8、`docs/plan/v0.4.md` 第 7 节、`experiments/E1-cross-language-search/protocol.md` 第 7 节。
性质：按第 7 节把搜索、推荐、翻译的下一笔范围标成继续、缩小、暂停，或在证据不够时标成未决定。本文件是过程记录。它不证明普遍有效，也不改写 2026-09-17 草稿。

基线是 `origin/main` 的 `8d7b951`。下面的运行记录在未合并分支上。本分支没有合并那些分支的代码。数字只来自那些路径里的文件。文件没有写出的总数、额度、命中率，这里不补。

## 1 相对 2026-09-17 草稿新增的真实证据

`docs/reports/w8-first-round-decision-2026-09-17.md` 保留不改。那份草稿写于零检索运行、零会话、零付费调用之后，并把搜索写成窄化、把自动候选写成暂停、把片段缺口检查写成继续。那些句子留在原文件。

2026-09-22 多出来的、已经落在文件里的证据是：

| 来源 | 分支与提交 | 运行目录 | 相对草稿的增量 |
|---|---|---|---|
| W4，PR #5 | `cursor/w4-e1-first-round-4e4f`，记录提交 `069ee17a34aec807fc83865b7fa6064a8a1204d4`；材料指针 `6010be0eee6d0e7f46ad851931741b81f741e0f0` | `experiments/E1-cross-language-search/runs/2026-09-22-w4-first/` | 开放题 A 组 20 次检索有返回；种子 A 组 8 次里 7 次有返回、1 次 403；45 条代理技术判定。B/C/M 请求数为 0 |
| W6，PR #7 | `cursor/w6-e3-e6-probe-cd86`，`839d7cb5cc51f4cea82cc9302a27f3d612193fcb` | `experiments/E3-faithful-reading/runs/2026-09-22-w6/` 与 `experiments/E6-api-probe/runs/2026-09-22-w6/` | 6 条公开片段经 Google Translate `client=gtx` 各译一次，并有技术核对。个人模型请求的记录行状态是未运行 |
| W7，PR #6 | `cursor/w7-release-metadata-e8-6a3c`，`8addaf19e2876eb7e5c794193befcd700c1dea64` | 无运行目录。材料在 `experiments/E8-discoverability/2026-09-22-retest-prepared.md` 等 | 只准备了简介、topics、入口查询和许可证备选。E8 复测未运行 |
| W5 | 无新分支、无会话记录 | `experiments/E2-open-ended-discovery/session-setup.md` 仍是未运行设置 | 没有新的会话证据 |

主分支上的 `experiments/E3-faithful-reading/translation-contrast-2026-09-18.md` 仍是空模板。它和 PR #7 的 gtx 记录是两份文件。`experiments/E8-discoverability/2026-09-17-probe.md` 与 `2026-09-18-retest.md` 未被 2026-09-22 的准备文件覆盖。

## 2 分范围结论

协议第 7 节：有可解释、可复核的额外好结果，才支持继续一轮，并同时报告本方案漏掉的好结果。C 与 B 相近时优先简单方案。C 与 M 相近时不宣传跨语言独有收益。差异只来自字段、请求数或翻译条件时，先修实验。没有增益时，定位接口、构题和检索策略，再用新批次复查。强对照同样好用时，讨论缩小或停止该路径。E1 只影响相应搜索投入，E2 单独报告。不用小样本百分点宣布产品成功。

三条范围都没有走完上述比较，所以结论都是未决定。证据不足。

<!-- w8-decisions -->
- 搜索：未决定
- 推荐：未决定
- 翻译：未决定
<!-- /w8-decisions -->

### 2.1 搜索

未决定。证据不足，不能在继续、缩小、暂停里选一项。

已核对的文件：`manifest.json`、`candidates.jsonl`（100 行，臂均为 A）、`judgments.jsonl`（45 行）、`report.md`。时间 `2026-09-22T01:43:35Z` 至 `2026-09-22T01:46:51Z`。`github_token_used` 为 false，间隔 7 秒，模型请求 0。`manifest.json` 里 `freeze.status` 仍是 `pointers-recorded-not-yet-run`；同一文件又有 `started_at`、`finished_at` 和候选行。检索是否发生，以候选、判定和请求计数为准。

A 组开放题：尝试 20，成功 20，失败 0，候选行 68。B、C、M：各 20 条 blocked，尝试请求 0，原因是变体覆盖缺失，文件写明 refusing to fabricate。D 的 `d_status` 是未运行。`e9_status` 是未展开。种子 A 组：尝试 8，成功 7，失败 1。失败任务是 `seed-zh2en-02`，错误文本为 `HTTP Error 403: rate limit exceeded`。该文件不另写剩余额度，本报告也不补额度。

判定人是 `agent:bc-74855d06-e3bc-5479-9555-dd499ba84e4f`。45 条的 `novel_to_judge` 与 `worth_following` 都是 `unknown`。判定备注写明非盲，判定人是代理。盲测完成这五个字不出现在运行记录里，本报告也不使用。

条款对照：

- 继续一轮需要可复核的额外好结果。C 的请求数是 0，没有跨语言额外结果。继续一轮的条件未出现。
- C 与 B、C 与 M 没有成对结果。相近或不相近都没有观察。字段只有默认字段，README 配对未做。
- 「没有增益」尚未建立，因为对照臂没有发出检索。词表机械匹配把 20 条开放题的 B/C/M 全部挡住，这是可指出的阻塞，不是增益结论。
- D 未运行。强对照同样好用这一条没有观察。

因此搜索范围保持未决定。W10 在 v0.4 里仍是条件性工作包；本批没有可复核的跨语言增益，那一进入条件未出现。这不把 W10 写成暂停。

A 组里、用途 `yes` 且硬条件 `satisfied` 的仓库（只属于臂 A，只来自 `judgments.jsonl`）：

- `zh2en-eval-01`：`13429837441/localShare`、`Maidehua/LanDrop`、`chengcheng84/rustysend`、`Hisakazu333/NekoDrop`
- `zh2en-eval-05`：`ron159/iGestures`、`Inonvation/cad-gesture`、`decajoin/mouse-gestures`、`ubuchow/MouseGesture`
- `en2zh-eval-01`：`FinchipAIOrg/housing-fund-loan-calculator`
- `en2zh-eval-05`：`magician000/DingTalkRobot-python`（同文件硬条件为 `satisfied`。同目录 `report.md` 这一条只写了用途符合，没有重复硬条件；以 JSONL 为准）

这些是原生查询的技术符合记录。它们不是 C 相对 A 的额外好结果。

反例（搜索）：

- 成功返回的 7 条已知目标里，指定仓库进入所保存前 30 的条数是 0。这是该批 A 组窗口内的计数。协议规定它不是全体召回，本报告不把它写成命中率。未进入窗口的目标：`marm00/cinema`、`Dark-Kernel/tuisic`、`tsirysndr/tunein-cli`、`danvergara/dblab`、`stephband/scribe`、`mar10/wsgidav`、`Yu-Core/SwashbucklerDiary`。查询来自来源短句反推。
- `seed-zh2en-02`（目标 `sunsations/speed_read`）是 403，不计入上面的 0。`candidates.jsonl` 没有这一行。
- `seed-en2zh-01` 至 `seed-en2zh-04` 在 `candidates.jsonl` 中没有行，manifest 里 `hit_at_30` 为 false、`status` 为 ok。文件没有 `total_count`，这里不补总数。
- 开放题在 `candidates.jsonl` 中没有行，因而没有前 5 可核对：`zh2en-eval-02`、`zh2en-eval-07`、`zh2en-eval-08`、`zh2en-eval-09`、`en2zh-eval-02`、`en2zh-eval-03`、`en2zh-eval-04`、`en2zh-eval-06`、`en2zh-eval-07`、`en2zh-eval-08`、`en2zh-eval-09`、`en2zh-eval-10`。0 行只说明这份记录里没有候选。
- `zh2en-eval-03`、`zh2en-eval-04`、`zh2en-eval-10` 以及已核对的种子 `seed-zh2en-01`、`seed-zh2en-03`、`seed-zh2en-04`，前 5 的用途都是 `no`。多条中文结果前排重复出现 `cirosantilli/china-dictatorship` 及其近似仓库，以及 `gege-circle/.github`。这是这些结果列表里的现象。
- `LumiaGG/TransportFile`（`zh2en-eval-01`）与 `zangjiahe/DingTalkRobot`（`en2zh-eval-05`）用途是 `yes`，硬条件是 `unknown`。后者备注写 README 404。未知不算满足。
- 部分符合且硬条件未知：`szboboxing/mouse-gesture-actions`、`guoyu07/thinksns-installer-plugin`、`v0v0/income-tax-calculator`。

未验证方向（搜索）：B、C、M 的实际检索；C 与 B、C 与 M 的比较；README 字段配对；D 对照；E9；人类判断者的新颖性和愿意继续看；有价值的新发现；英文使用者体验。开放题里 0 行的任务，没有候选可标成被漏掉的好仓库。

### 2.2 推荐

未决定。证据不足。

E2 按协议单独报告。W5 的发起人短会话没有发生。仓库里只有 `experiments/E2-open-ended-discovery/session-setup.md` 这份未运行设置。没有会话记录，因此没有起点、候选、反馈、耗时或有价值新发现可以引用。

E2a 有具体价值，才谈得上 W9。这次没有这种记录。自动候选有增益或没有增益，都没有观察。未运行不能写成无收益，也不能写成有收益。推荐范围因此未决定。W9、W10 的进入条件未出现，本文件不把它们写成暂停。

反例（推荐）：没有。未发生的会话产生不了反例。

未验证方向（推荐）：两对短会话、展示与略过的候选、人工准备时间、顺序、中文发起人反馈、英文使用者体验、自动获取与排序。

### 2.3 翻译

未决定。证据不足。

已核对：`experiments/E3-faithful-reading/runs/2026-09-22-w6/` 的 `fragments.jsonl`（6 条，冻结时间 `2026-09-22T02:05:13Z`）、`translations.jsonl`、`judgments.jsonl`、`observations.jsonl`、`manifest.json`、`report.md`，以及 E6 的 `probe.jsonl` 与 `manifest.json`。

实际工具是 Google Translate 公开接口，`client=gtx`，主机 `translate.googleapis.com`。6 次 HTTP 状态都是 200。`elapsed_ms` 按 P-01 至 P-06 为 1146、653、908、532、686、288，单位毫秒，只属于这次请求。工具版本是未知。`translations.jsonl` 没有费用字段，这里不补费用。冻结前另有短句「连接探测」译成 `connection detection`，HTTP 200；manifest 写明它不是六条判定。

判定人 `w6-technical-check`，身份是技术核对。方向：P-01、P-02、P-03 为中文到英文（`hiroi-sora/Umi-OCR`）；P-04 为英文到中文（`expressjs/express`）；P-05、P-06 为英文到中文（`psf/requests`）。

改变了理解，且 `severe_mistranslation` 为 yes 的条目：

- P-01：反引号中的选项名被译成英文，「自然段」写成 segment。否定「不区分多栏布局」仍在。
- P-04：「does not force」仍是「不会强迫」。原文在 `over` 与 `14` 之间换行，译文里「超过」没有修饰 14。链接还在。
- P-05：第一行 `import requests` 被写成「导入请求」。下一行的 `requests.get` 和 URL 还在。

本批没有记成严重误译的条目：

- P-02：忽略范围「整个文本块而不是单个字符」还在，三个标识符原样保留。
- P-03：先看源码、再得出 Mac 没法用，这层关系还在。
- P-06：`but` 之后的不修还在。`more trouble than not` 收成了「会造成更多麻烦」，比较对象没有了；判定仍把这句记为非严重。`git fsck` 文本还在，反引号变成中文引号。

这 6 条计数只描述这 6 条和 gtx。E3 协议写明它不是准确率，也不由此决定自建翻译。v0.4 第 7 节里「现成翻译足够则减少自建」需要现成基线已经够用。阅读基线工具沉浸式翻译的状态是未运行，Chrome 内置翻译界面的状态是未运行。gtx 上已有 3 条改变理解的记录，因此也不能把 gtx 在这 6 条上写成足够。自建翻译比较的状态是未运行。有缺口才比较自建这一步还没有做，是否做也未决定。

E6：`probe.jsonl` 的 `status` 是未运行，`sent_requests` 是 0，`actual_requests` 是 0。原因是 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 均未设置。`elapsed_ms`、三项用量、`model`、`base_url`、`model_output`、`account_quota` 在文件里都是未知或未运行。`billing_note` 是未发送请求、本次零费用。没有余额数字。费用不可接受这一条没有观察。

反例（翻译）：上面 P-01、P-04、P-05。它们反驳的是「gtx 在这 6 条上没有改变理解」。它们不扩展成基线工具的结论，也不扩展成必须自建。

未验证方向（翻译）：沉浸式翻译、Chrome 内置翻译界面、自建翻译比较、整仓库翻译、语言使用者体验、个人模型的格式、延迟、用量与错误分类、账户配额。

## 3 未运行清单

凡下面各项，文件状态都是未运行。本报告没有把它们写成已测指标。

<!-- w8-unrun -->
- W5：未运行
- E6 个人模型：未运行
- E8 复测：未运行
- E9：未运行
- D 对照：未运行
- 使用者是否愿意继续看：未运行
<!-- /w8-unrun -->

同时未运行或未展开、且没有被写成指标的还有：有价值的新发现、沉浸式翻译、Chrome 内置翻译界面、自建翻译比较、README 配对诊断、H0 占比、搜索剩余额度。E8 的可见总数与名次也没有写入本文件。E8 的 23 条入口查询在 PR #6 的 `entry-queries.jsonl` 里 `status` 都是未运行，`result` 都是 null。未运行不是零结果。2026-09-18 的 403 记录仍是「读元数据即限流、搜索未发起」，不是新的排名。

名称、许可证、模型供应商仍是待决策，见 `docs/decisions/0001`、`0002`、`0003`。本轮没有改仓库名，没有添加 LICENSE，没有把密钥写入仓库。

## 4 各工作包四项

| ID | 做了什么 | 证据在哪里 | 失败或未知 | 下一输入是否具备 |
|---|---|---|---|---|
| W4 | 未合并分支上跑了 A 组检索和代理技术核对 | PR #5，`runs/2026-09-22-w4-first/` | B/C/M 请求 0；D 未运行；E9 未展开；1 次 403；新颖性与愿意继续看为 unknown | 可比较的 B/C/M 或 D 仍缺；搜索范围未决定 |
| W5 | 没有会话 | 主分支 `session-setup.md` 仍标未运行 | 无会话记录 | 仍缺发起人短会话；推荐范围未决定 |
| W6 | 未合并分支上完成 6 条 gtx 译文与技术核对；个人模型记录写成未运行 | PR #7 两个 `runs/2026-09-22-w6/` | 基线工具与 Chrome 界面未运行；模型延迟、用量、配额未知 | 翻译范围未决定 |
| W7 | 未合并分支上准备了元数据草案 | PR #6 | 未写入仓库设置；E8 复测未运行 | 复测输入仍缺一次真实搜索 |
| W8 | 本报告 | 本文件 | 三方向均为未决定 | 缺第 3 节所列未运行项 |

## 5 将改路径

写本文件之前列出的路径：

- 新增 `docs/reports/w8-first-round-decision-2026-09-22.md`（本文件）
- 更新 `docs/backlog.md` 的日期说明与 W4、W5、W6、W7、W8 状态行
- 新增 `experiments/E1-cross-language-search/scripts/test_w8_decision_2026_09_22.py`

不改 `docs/reports/w8-first-round-decision-2026-09-17.md`、`docs/plan/v0.3.md`、`docs/plan/v0.4.md`，不改 W4、W6、W7 的实现，不添加 LICENSE，不改仓库名，不写扩展、manifest、content script 或 service worker。

## 6 测试

```bash
python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_w8_decision_2026_09_22.py"
```

测试检查本文件存在、09-17 草稿字节未改、三条结论为未决定、第 3 节未运行项仍是未运行，以及未运行项没有被写成百分比、额度或个人模型耗时。结果以当次运行输出为准。
