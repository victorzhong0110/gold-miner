# E1 默认字段与 README 字段配对（2026-09-28-readme-pair）

对应协议第 3 节：README 扩展是另一轮配对诊断，和默认字段分开报告。
同一会话里，每条原始查询先按默认仓库搜索请求一次，再追加 `in:readme` 请求一次。
查询词没有改写。这不是 B/C/M，也不是跨语言增益。

## 1 做了什么

- 运行 `2026-09-28-readme-pair`。材料指针仍是 `6010be0eee6d0e7f46ad851931741b81f741e0f0`。
- 时间：2026-09-28T14:47:21Z 至 2026-09-28T14:56:48Z。
- `github_token_used` 为 false。间隔 8.0 秒。
- 模型请求 0。D 未运行。E9 未展开。B/C/M 未运行。
- 用途适合、硬条件、是否值得继续看：未运行。

## 2 请求

- 尝试请求 56，成功 56。
- 限流后停止后续请求：false。

失败或取消的原文留在 `manifest.json`。这里不另写剩余额度。

## 3 同一会话窗口

两边都成功时才比较仓库集合。0 条只说明这次返回的窗口里没有候选。
数字只统计这次保存的前 30，不外推到窗口之外。

| 任务 | 侧 | 默认状态 | README 状态 | 两边都有 | 仅默认 | 仅 README |
|---|---|---|---|---|---|---|
| `zh2en-eval-01` | eval | ok | ok | 2 | 12 | 28 |
| `zh2en-eval-02` | eval | ok | ok | 0 | 0 | 4 |
| `zh2en-eval-03` | eval | ok | ok | 0 | 12 | 30 |
| `zh2en-eval-04` | eval | ok | ok | 0 | 15 | 30 |
| `zh2en-eval-05` | eval | ok | ok | 0 | 12 | 30 |
| `zh2en-eval-06` | eval | ok | ok | 0 | 1 | 30 |
| `zh2en-eval-07` | eval | ok | ok | 0 | 0 | 0 |
| `zh2en-eval-08` | eval | ok | ok | 0 | 0 | 30 |
| `zh2en-eval-09` | eval | ok | ok | 0 | 0 | 0 |
| `zh2en-eval-10` | eval | ok | ok | 0 | 9 | 30 |
| `en2zh-eval-01` | eval | ok | ok | 1 | 1 | 10 |
| `en2zh-eval-02` | eval | ok | ok | 0 | 0 | 30 |
| `en2zh-eval-03` | eval | ok | ok | 0 | 0 | 30 |
| `en2zh-eval-04` | eval | ok | ok | 0 | 0 | 1 |
| `en2zh-eval-05` | eval | ok | ok | 0 | 2 | 30 |
| `en2zh-eval-06` | eval | ok | ok | 0 | 0 | 30 |
| `en2zh-eval-07` | eval | ok | ok | 0 | 0 | 30 |
| `en2zh-eval-08` | eval | ok | ok | 0 | 0 | 30 |
| `en2zh-eval-09` | eval | ok | ok | 0 | 0 | 30 |
| `en2zh-eval-10` | eval | ok | ok | 0 | 0 | 11 |
| `seed-zh2en-01` | seed | ok | ok | 0 | 9 | 30 |
| `seed-zh2en-02` | seed | ok | ok | 0 | 7 | 30 |
| `seed-zh2en-03` | seed | ok | ok | 0 | 11 | 30 |
| `seed-zh2en-04` | seed | ok | ok | 0 | 12 | 30 |
| `seed-en2zh-01` | seed | ok | ok | 0 | 0 | 30 |
| `seed-en2zh-02` | seed | ok | ok | 0 | 0 | 30 |
| `seed-en2zh-03` | seed | ok | ok | 0 | 0 | 30 |
| `seed-en2zh-04` | seed | ok | ok | 0 | 0 | 20 |

### 默认窗口为 0、README 窗口有候选时的前 5 个仅 README 仓库

- `zh2en-eval-02`：`wtwang1998/awesome-toolkit`、`wendygaoyuan/tool`、`elwina/VibeArk`、`ZpFhnu/vibe-coding-cases`
- `zh2en-eval-08`：`3257085208/NIE-Higan-Blog`、`sopig/WholeProject`、`tnfe/TNT-Weekly`、`lutaooooo/tds-website`、`sunshineLixun/astro_stripe_landing_page`
- `en2zh-eval-02`：`seanzhou1023/awsome-python`、`nixawk/hello-python2`、`gribouille/awesome-python`、`solarlee/Awesome-Python-Toolbox`、`uhub/awesome-php`
- `en2zh-eval-03`：`lukasz-madon/awesome-remote-job`、`vinta/awesome-python`、`aigc-apps/sd-webui-EasyPhoto`、`avelino/awesome-go`、`public-apis/public-apis`
- `en2zh-eval-04`：`punkpeye/awesome-mcp-servers`
- `en2zh-eval-06`：`oz123/awesome-c`、`GitHubDragonFly/GitHubDragonFly.github.io`、`vicky002/1000_Projects`、`joshuatz/linkedin-to-jsonresume`、`RistBS/Awesome-RedTeam-Cheatsheet`
- `en2zh-eval-07`：`jxzzlfh/awesome-stars`、`NetW0rK1le3r/awesome-hacking-lists`、`weiruankeji2025/weiruan-Netdisk`、`wangbo5825/BaiduNetdiskImport`、`wangjiezhe/awesome-stars`
- `en2zh-eval-08`：`rohitg00/awesome-openclaw`、`punkpeye/awesome-mcp-servers`、`ZJU-REAL/HugAgentOS`、`LHL3341/awesome-claws`、`ikaijua/Awesome-AITools`
- `en2zh-eval-09`：`jivoi/awesome-osint`、`uhub/awesome-python`、`marekbrze/categorized-raycast-extensions`、`aneasystone/github-trending`、`jxzzlfh/awesome-stars`
- `en2zh-eval-10`：`thedaviddias/llms-txt-hub`、`bilalpiaic/Easy-Books`、`nbox/ProductHunt-Statistic`、`LinXiaoTao/awesome-grokbot`、`SatangThevalue/ai-skills`
- `seed-en2zh-01`：`mgramin/awesome-db-tools`、`vinta/awesome-python`、`xo/usql`、`avelino/awesome-go`、`danvergara/dblab`
- `seed-en2zh-02`：`Fechin/reference`、`Solido/awesome-flutter`、`bradtraversy/design-resources-for-developers`、`sindresorhus/awesome`、`vsouza/awesome-ios`
- `seed-en2zh-03`：`awesome-selfhosted/awesome-selfhosted`、`avelino/awesome-go`、`may215/awesome-termux-hacking`、`punkpeye/awesome-mcp-clients`、`ripienaar/free-for-dev`
- `seed-en2zh-04`：`fluttergems/awesome-open-source-flutter-apps`、`dkhamsing/open-source-ios-apps`、`awesome-dsh-plugin/awesome-dsh-plugin`、`ever-works/awesome-time-tracking`、`Correia-jpv/fucking-open-source-ios-apps`

这些前排名字里有的包含 awesome。这只描述列出的名字，不是对全部候选的种类判定。

完整候选在 `candidates.jsonl`。上表没有出现的仓库不代表不存在。

### 已知目标是否进入该侧前 30

只对种子任务。未进入窗口不等于全体找不到。请求没成功则记未比较。

- `seed-zh2en-01` 目标 `marm00/cinema`：默认 未进入窗口；README 未进入窗口。
- `seed-zh2en-02` 目标 `sunsations/speed_read`：默认 未进入窗口；README 未进入窗口。
- `seed-zh2en-03` 目标 `Dark-Kernel/tuisic`：默认 未进入窗口；README 未进入窗口。
- `seed-zh2en-04` 目标 `tsirysndr/tunein-cli`：默认 未进入窗口；README 未进入窗口。
- `seed-en2zh-01` 目标 `danvergara/dblab`：默认 未进入窗口；README 第 5。
- `seed-en2zh-02` 目标 `stephband/scribe`：默认 未进入窗口；README 未进入窗口。
- `seed-en2zh-03` 目标 `mar10/wsgidav`：默认 未进入窗口；README 未进入窗口。
- `seed-en2zh-04` 目标 `Yu-Core/SwashbucklerDiary`：默认 未进入窗口；README 未进入窗口。

## 4 失败或未比较

- 两侧请求都有返回。返回 0 条候选仍算这次请求成功。

## 5 匹配字段

README 侧候选的 `matched_fields` 来自接口的 `text_matches`。接口没有给出可映射字段时保持 unknown，不改写成 readme。
- 默认侧：description 102 行；description,name 4 行。
- README 侧：unknown 677 行。

配对的 56 次之外，为核对响应形状又发了 1 次 GET，不计入上面的请求数。
查询与 `seed-en2zh-01` 的 README 侧相同。`text_matches` 长度为 0。
前 5 名：`mgramin/awesome-db-tools`、`vinta/awesome-python`、`xo/usql`、`avelino/awesome-go`、`danvergara/dblab`。

## 6 不能下的结论

协议第 7 节的继续、缩小或暂停：未决定。
B/C/M 未运行，不能把字段差异写成跨语言增益。
用途判定未运行。有价值的新发现：未运行。
D 未运行。E9 未展开。
