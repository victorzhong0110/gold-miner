# 工程前置检查

状态：检查清单与已知约束，2026-09-17 整理。写扩展代码（第 1b 阶段）前逐项过；每项过完在末尾"记录"处写日期与结果文件。  
依据：GitHub 与 Chrome 官方文档（v0.3 第 10 节链接）与 2026-09-17 的 API 探测；标"需实测"的项没有现成证据。

## 1 GitHub Search API

已知约束：

- 配额：认证 30 次／分钟，未认证 10 次／分钟。与核心 API 的 5,000 次／小时分开计。
- 单条查询最多返回 1,000 条；查询串不超过 256 字符，逻辑操作符不超过 5 个。
- 默认字段：名称、简介、topics。README 需显式 `in:readme`，明显慢，且对总量大的词可能超时。
- `language:` 指代码语言，不是文档语言；不能用来筛"中文 README"。
- 并发请求容易触发二级限流。探测时串行、间隔 2 秒未触发。
- 请求头 `Accept: application/vnd.github.text-match+json` 可返回匹配到的字段与片段，用于记录"命中来自名称、简介还是 README"；README 片段是否返回需实测。这是 E1 记录"来源路径"的直接依据。

含义：

- 一次用户搜索改写成 2–4 条查询（中英各 1–2 条），再加 `in:readme` 变体，一分钟内多搜两次就撞未认证上限。v0.3 说"若额度不足再评估用户自备 GitHub 凭据"，判断是大概率需要。
- 设计：支持用户配置 GitHub 细粒度 PAT（只授予 Public repositories 只读）；未配置时降级为只做原生查询加一条译词查询，界面显示"未配置 GitHub 凭据，跨语言覆盖受限"。
- 缓存搜索结果，键为规范化后的查询串，短期内相同页面与兴趣不重复请求（v0.3 第 3 节）。

需实测：细粒度 PAT 对 search 端点的接受情况；`text_matches` 是否覆盖 README。

记录：

## 2 中文查询在站内搜索的实际表现

问题：GitHub 仓库搜索对 CJK 查询与 `in:readme` 的召回不清楚。若中文用途词基本搜不到中文 README，跨语言路径不能依赖站内 README 搜索，需要换候选来源或换策略。这是 H1 的技术前置，约一小时。

步骤：

1. 取 10 个已知 README 仅中文、stars 在 50 以上的仓库（可从 E1 种子集构造过程中顺手取，见 [E1 协议](../../experiments/E1-cross-language-search/protocol.md) 第 3 节）。
2. 每个仓库从其 README 里抄 2 个用途短语（一个 2–4 字词，一个 6–10 字短语），不改写。
3. 对每个短语跑三条查询：原样、`in:readme`、`in:description`；各取前 30。
4. 记录目标仓库是否出现及名次；另记同一短语加空格切分、加引号后的差异。

判定：

- `in:readme` 对 6–10 字短语召回率低于一半：站内 README 搜索不能作为中文侧主要路径。候选来源改为简介与 topics 加模型生成的多语言关键词，并考虑补充来源（HelloGitHub 索引、awesome 清单、GitHub topics 页）。把结论写进 E1 协议第 4 节。
- 召回可用：保留 `in:readme` 变体，但限制在无其他结果时触发，控制配额。

记录：

## 3 GitHub 页面接入

已知约束：

- GitHub 使用 Turbo 导航，站内跳转不整页刷新。content script 只在 `DOMContentLoaded` 注入会漏掉后续页面。需要监听 Turbo 导航事件（如 `turbo:load`、`turbo:render`）并对局部渲染用 `MutationObserver` 等待目标元素出现。事件名以当前 GitHub 前端为准，需实测。
- 部分页面（代码浏览、搜索结果）为客户端渲染，目标元素在导航事件后才出现。
- GitHub 的页面 CSP 不影响 content script 的隔离世界，但禁止向页面注入内联脚本。不要这样做。
- GitHub 自身 CSS 很重。注入的界面用 Shadow DOM 隔离样式，避免双向污染。
- 选择器会随 GitHub 改版失效。每个注入点写一个"找不到锚点就静默退出并计数"的守卫，不抛错到页面。

参考实现：[Refined GitHub](https://github.com/refined-github/refined-github)（MIT）。看它如何监听导航、等待元素、组织按页面类型启用的功能，以及选择器失效时的处理。不必复用其构建体系。

需实测：当前 GitHub 前端派发的导航事件名；仓库页 README 容器、issue 评论容器的稳定锚点。

记录：

## 4 扩展架构（MV3）

分层与 v0.3 第 7 节一致，补充 MV3 的具体约束：

- content script：只负责读取页面 DOM、渲染注入界面、把"需要翻译的段落"与"当前仓库上下文"发给 service worker。不持有任何密钥，不直接请求模型端点。
- service worker：GitHub API 与模型 API 的所有请求、任务队列、缓存读写、预算计数。
- 存储：偏好与配置用 `chrome.storage.local`（不用 `sync`，密钥不应经 Google 账号同步）；译文缓存与搜索缓存用 IndexedDB，并申请 `unlimitedStorage`，因为 `storage.local` 默认约 10 MB。
- 权限：固定 `storage`、`unlimitedStorage`、`https://github.com/*`、`https://api.github.com/*`；模型端点用 `optional_host_permissions` 按用户配置的 origin 动态申请（[决策 0002](../decisions/0002-model-endpoint-config.md)）。
- service worker 生命周期：空闲约 30 秒会被终止，进行中的 fetch 能延长存活，但长队列不能依赖内存状态。任务队列与进度必须落到存储，重启后可恢复；取消标记也要落存储。
- 消息：content script 与 service worker 之间用 `chrome.runtime` 消息或 `Port`；对长任务用 Port 推送逐段结果，实现 v0.3"逐段呈现"。

## 5 内容获取与缓存失效

- 当前打开的仓库页：README 已在 DOM 中，直接按块级元素分段（标题、段落、列表项、表格单元格、代码块原样保留），不再请求 API。
- 候选仓库（未打开）：用 `GET /repos/{owner}/{repo}/readme`，请求头 `Accept: application/vnd.github.raw+json` 取原文；响应含 blob SHA，作为 v0.3 第 4 节"原文内容校验值"的一部分。
- 失效：以段落文本哈希为主键，以 README blob SHA 与抓取时间为版本。再次访问时先用条件请求（`If-None-Match`）检查 README 是否变化，304 不计入核心 API 配额。
- 核心 API 配额：认证 5,000 次／小时，未认证 60 次／小时。未配置 PAT 时候选仓库的 README 抓取要节制，只对用户点开的候选抓取。

## 6 费用与调用控制

供应商无关地实现（[决策 0002](../decisions/0002-model-endpoint-config.md)）：

- 每个页面会话的模型请求上限（默认值待第 1b 实测后定），到达即暂停并显示。
- 相同段落哈希的请求合并；并发上限 2；重试上限 2，指数退避；所有请求带 `AbortController`，用户离开页面或点取消时中止。
- 本地计数器：请求数、失败数、重试数、缓存命中数、估算 token 数，界面可见，导出为 E6 记录。
- 自动生成可整体暂停；暂停状态跨页面保持。

## 7 密钥边界

- 密钥只在 service worker 内存与 `chrome.storage.local` 出现。
- 不写日志；错误对象在记录前脱敏（替换 `Authorization` 头与 `sk-` 前缀串）。
- 导出译文包、研究记录、诊断信息前，对整个导出文本做一次密钥模式扫描，命中即阻止导出。
- 测试：配置密钥后遍历页面 DOM 与捕获的 console 输出，断言密钥子串不出现。

## 8 测试清单（对应 v0.3 第 7 节"验证与交付要求"）

- 跨语言候选：固定一组查询与录制的 API 响应，断言合并去重后每个候选带来源路径。
- 重复请求：同一页面重复触发，断言模型请求数不增加。
- 源文变更：修改录制的 README，断言只有变化段落被重新翻译，其余命中缓存。
- 密钥不进入网页或日志：第 7 节的测试。
- 限流与失败恢复：注入 403／429／5xx 与网络中断，断言退避、上限、暂停与恢复行为，以及界面状态。
- 命令与链接保持完整：对含代码块、行内代码、链接、表格的 README 做翻译前后结构对比，断言代码与链接目标逐字不变。
- 探索状态保持：Turbo 导航往返后，断言兴趣、已排除项与上一条探索路径仍在。
- service worker 重启：模拟终止后恢复，断言队列继续、无重复请求。

用真实失败案例补回归用例，不以全部成功的模拟替代真实来源验证（v0.3 原话）。
