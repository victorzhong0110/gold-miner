# E1 D 组运行 2026-10-04-d-minimax

- 批次：`eval.batch_1`。协议第 3 节 D 组，联网助手强对照。
- 模型：`MiniMax-M3`。端点：`POST /v1/responses`，服务端工具 `web_search`。
- 决定：docs/decisions/0004-minimax-d-group.md（2026-10-04）。输出上限 8192。
- 材料提交：`eae2d4c14b52339f12af05ca1a41a28f82fb30bf`（首轮）。续跑 runner 提交：`314c2a75e55f2455657500dcad3a49e99d9724e7`。
- 开始 2026-10-04T11:13:52Z，结束 2026-10-04T12:50:25Z（UTC）。修复后的 runner 调用 1 次（见 checkpoint.json `invocations`；首轮调用未逐次记录）。
- 状态：`complete`。

## 任务

- 任务完成 20 / 20。失败（可续跑重试）0。未尝试 0。
- 「完成」= 模型返回可解析名单且 GitHub 核对已跑完。超时、HTTP 错误、没有可解析名单的任务不算完成，续跑时重新请求模型。
- 经过重试才完成：`zh2en-eval-08`（先前 timeout，共请求 2 次），`en2zh-eval-01`（先前 timeout，共请求 2 次），`en2zh-eval-03`（先前 bad_response，共请求 2 次）。
- 模型请求 23（含失败与重试；参数重试也计入）。GitHub 核对请求 177（含跳转跟随与重核）。
- 服务端 web_search 调用（响应里可见的）：全部请求合计 126；完成任务的最终回答合计 126。完成任务里模型没发起搜索的 0。
- 可见 token（全部请求合计）：输入 1151179，其中缓存 626595；输出 9356。缺计数的请求不计入，不把 null 当成 0。
- 可见费用：未知。
- 人工用途判断：未运行。阅读对照：未运行。B/C/M 在本模型上：未运行。

## 仓库核对

- 完成任务里模型提名 172 个（每题最多 10，题内去重）。
- GitHub 存在 169（公开 169，私有 0）。其中经 301/302 跳转（改名或转移）跟随后存在 3。
- 幻觉（GitHub 404）3。幻觉率（占提名）3/172 = 1.7%。
- 核对未决（跳转跟不到、GitHub 限流或错误，续跑时重核）0。
- 公开存在、写入 candidates.jsonl 的去重仓库 169。

| 任务 | 模型给的名字 | GitHub 跳转 | 现名（canonical_repo） |
|---|---|---|---|
| zh2en-eval-04 | twwch/Mako | 301 → https://api.github.com/repositories/1105761331 | LingyiChen-AI/Mako |
| zh2en-eval-08 | davidmerfield/Blot | 301 → https://api.github.com/repositories/50626524 | blotcms/blot |
| en2zh-eval-07 | Wjavan/Direct-download-link | 301 → https://api.github.com/repositories/1335635946 | Wjavan/FerryLink |

404 名单：`Rabbendebiene/Gesturefy`（zh2en-eval-05），`composer/composer-bin-plugin`（zh2en-eval-06），`b3log/baidu-netdisk-downloaderx`（en2zh-eval-07）。

failures.jsonl 是只追加的事件记录。上面数字取每个任务、每个名字的最新状态；较早的 timeout / bad_response / github_migrated 行若已被后来的成功覆盖，在这里不再算失败。

尚未完成：无

## 每题

| 任务 | D 状态 | 模型请求 | web_search | 提名 | 存在 | 404 | 跳转 | 未决 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| zh2en-eval-01 | 完成 | 1 | 1 | 9 | 9 | 0 | 0 | 0 |
| zh2en-eval-02 | 完成 | 1 | 8 | 9 | 9 | 0 | 0 | 0 |
| zh2en-eval-03 | 完成 | 1 | 8 | 10 | 10 | 0 | 0 | 0 |
| zh2en-eval-04 | 完成 | 1 | 2 | 8 | 8 | 0 | 1 | 0 |
| zh2en-eval-05 | 完成 | 1 | 2 | 10 | 9 | 1 | 0 | 0 |
| zh2en-eval-06 | 完成 | 1 | 2 | 6 | 5 | 1 | 0 | 0 |
| zh2en-eval-07 | 完成 | 1 | 10 | 10 | 10 | 0 | 0 | 0 |
| zh2en-eval-08 | 完成 | 2 | 5 | 10 | 10 | 0 | 1 | 0 |
| zh2en-eval-09 | 完成 | 1 | 6 | 4 | 4 | 0 | 0 | 0 |
| zh2en-eval-10 | 完成 | 1 | 4 | 10 | 10 | 0 | 0 | 0 |
| en2zh-eval-01 | 完成 | 2 | 12 | 9 | 9 | 0 | 0 | 0 |
| en2zh-eval-02 | 完成 | 1 | 4 | 10 | 10 | 0 | 0 | 0 |
| en2zh-eval-03 | 完成 | 2 | 11 | 9 | 9 | 0 | 0 | 0 |
| en2zh-eval-04 | 完成 | 1 | 2 | 10 | 10 | 0 | 0 | 0 |
| en2zh-eval-05 | 完成 | 1 | 1 | 10 | 10 | 0 | 0 | 0 |
| en2zh-eval-06 | 完成 | 1 | 6 | 10 | 10 | 0 | 0 | 0 |
| en2zh-eval-07 | 完成 | 1 | 12 | 9 | 8 | 1 | 1 | 0 |
| en2zh-eval-08 | 完成 | 1 | 12 | 10 | 10 | 0 | 0 | 0 |
| en2zh-eval-09 | 完成 | 1 | 8 | 5 | 5 | 0 | 0 | 0 |
| en2zh-eval-10 | 完成 | 1 | 10 | 4 | 4 | 0 | 0 | 0 |

## 与历史 A 组的仓库集合交集

A 组来自 `runs/2026-09-22-w4-first`（2026-09-22，无模型，B/C/M 当时全部 blocked）。这是仓库全名集合的交集，不是用途适合度，也不是同一时刻的配对实验。协议第 7 节「强对照同样好用」需要用途判断，本批该项未观察。

本批 20 题：D 存在仓库 169，该次 A 组候选 68，交集 0，只在 D 出现 169。

| 任务 | D 状态 | D 存在 | A 条数 | 交集 | 只在 D |
|---|---|---:|---:|---:|---:|
| zh2en-eval-01 | 完成 | 9 | 15 | 0 | 9 |
| zh2en-eval-02 | 完成 | 9 | 0 | 0 | 9 |
| zh2en-eval-03 | 完成 | 10 | 12 | 0 | 10 |
| zh2en-eval-04 | 完成 | 8 | 15 | 0 | 8 |
| zh2en-eval-05 | 完成 | 9 | 12 | 0 | 9 |
| zh2en-eval-06 | 完成 | 5 | 1 | 0 | 5 |
| zh2en-eval-07 | 完成 | 10 | 0 | 0 | 10 |
| zh2en-eval-08 | 完成 | 10 | 0 | 0 | 10 |
| zh2en-eval-09 | 完成 | 4 | 0 | 0 | 4 |
| zh2en-eval-10 | 完成 | 10 | 9 | 0 | 10 |
| en2zh-eval-01 | 完成 | 9 | 2 | 0 | 9 |
| en2zh-eval-02 | 完成 | 10 | 0 | 0 | 10 |
| en2zh-eval-03 | 完成 | 9 | 0 | 0 | 9 |
| en2zh-eval-04 | 完成 | 10 | 0 | 0 | 10 |
| en2zh-eval-05 | 完成 | 10 | 2 | 0 | 10 |
| en2zh-eval-06 | 完成 | 10 | 0 | 0 | 10 |
| en2zh-eval-07 | 完成 | 8 | 0 | 0 | 8 |
| en2zh-eval-08 | 完成 | 10 | 0 | 0 | 10 |
| en2zh-eval-09 | 完成 | 5 | 0 | 0 | 5 |
| en2zh-eval-10 | 完成 | 4 | 0 | 0 | 4 |

A 组那次还跑了不在本批的任务，不计入上表合计：seed-zh2en-01（9 条），seed-zh2en-03（11 条），seed-zh2en-04（12 条）。

## 不能下的结论

不能由这份名单宣布跨语言增益、产品效果或应该缩小功能。人工判断未运行。B、C、M 未在本模型上运行。费用未知。
「存在」只说明 GitHub 上有这个仓库，不说明它适合用户原话里的需求；与 A 组交集低也不说明哪一组更好用。幻觉率只按 GitHub 404 计，不含存在但答非所问的仓库。
