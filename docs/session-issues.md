# 会话问题清单

发起人真机操作中遇到的问题，逐条记录，等证据齐了批量修。
维护者：Mavis。首次记录 2026-10-04（第 1、2 项执行期间）。

与 `docs/backlog.md`（工作包）、`docs/known-limitations.md`（产品限制）不重复：
这里只放**真机操作暴露出来的问题**，修完应回流到上面两份之一。

## 2026-10-05 批量修复结果

S1–S6 全部已修并有回归锁定。O1 仍是观察，不是缺陷。
本节只记录修了什么和凭什么判定修好；**不构成 E1/E2/E3 任何效果证据**，
模型路径在发起人复测前仍算「未验证」。

| 编号 | 处置 | 回归锁定 |
|---|---|---|
| S1 假成功绿灯 | 探测改读输入框当前值；改动任一 BYOK 字段即清空状态栏；结果带实际被测主机 | `test_content.mjs` 无；浏览器验收 `probe-reads-the-input-box-not-stale-storage`、`editing-byok-clears-a-stale-success-light` |
| S2 默认主机无文档 | 改为 `api.minimaxi.com`（官方文档有列），并在文件里并列标注三个主机的区域与实测状态 | `test_check_byok_connection.py::TestExampleEnv` |
| S3 区域错配无提示 | 401/403 在区域主机上归类为 `wrong_region`（业务码 1004 同样）；记录带 `host_region` 与处置建议 | `TestRegionMismatch`（5 项） |
| S4 D 组只有 stub | 改为**录入 + 比较**：新增 `e1_d_control.py`，harness 接 `--d-input`；命中/幻觉/未核实三者分开 | `test_e1_d_control.py`（17 项） |
| S5 面板落在长页面底部 | 改为插到内容容器**顶部**；无锚点时固定定位悬浮，不再静默追加到 body 末尾 | `test_content.mjs` 两项 + 浏览器验收 `panel-is-visible-without-scrolling-on-a-long-results-page` |
| S6 ★阻塞项 | `max_tokens` 256 → 2048（单一常量）；显式剥离 `<think>`；探测校验内容而非只看状态码 | `test_shared.mjs` 4 项、`test_background.mjs` 4 项、`TestReasoningModelOutputs` 4 项 |

S6 补充说明：旧探测只验 `resp.ok`，所以选项页绿灯、终端 `check_byok_connection.py`
和真实模型请求**三处全绿而功能是坏的**。现在三处共用同一套判定
（`stripReasoning` + `readModelChoice` / `classify_http`），状态码 200 但
`finish_reason: "length"` 或只有思考内容，一律报失败而不是成功。

验证：离线套件 `python3 scripts/run_offline_suite.py` exit 0，
293 Python + 65 Node 通过；Chromium fixture 验收 12 项全绿
（[记录](reports/browser-acceptance-2026-10-05.json)），其中 3 项是本轮新增。
两者都是 fixture/自动证据，**不等于发起人真机复测**。

## 已修（2026-10-04 记录，2026-10-05 处置）

### S1 探测绿灯不随输入变化清空（假成功）

- 位置：`extension/src/options.js:120-154`（探测）、`load()`（回填输入框）
- 现象：探测从 `chrome.storage.local` 读取端点（`options.js:121`），
  **不读输入框当前值**；`show()` 只在保存/探测时调用，输入框改动不会清空状态栏。
- 后果：输入框里写着一个完全错误的端点，状态栏仍显示上一次探测的
  `http 200 ok`。使用者会把绿灯当成当前配置的绿灯。
- 实测：2026-10-04 输入框显示 `https://api.minimax.com/v1`（该域名无 DNS 记录），
  状态栏同时显示 `http 200 ok`。真实配置其实是另一个能用的主机。
- 为什么重要：本项目的核心纪律是「没有真实运行就写未运行」。一个不对应当前配置的
  绿灯，正是最容易让人误以为已有证据的那类缺陷。
- 候选修法（未决定）：
  1. 对输入框绑定 `input`/`change` 事件，改动即清空状态栏；
  2. 探测改为读输入框当前值，而不是只读存储；
  3. 状态栏显示实际被测主机，例如 `http 200 ok (api.minimaxi.com)`。

### S2 `config/byok.example.env` 默认主机不在官方文档（已修）

- 位置：`config/byok.example.env:5`
- 现状：默认 `https://api.minimax.cn/v1`。MiniMax 官方文档列出的是
  `https://api.minimax.io/v1`（国际）与 `https://api.minimaxi.com/v1`（大陆）。
  `.cn` 实测可用（HTTP 200），但官方文档未列。
- 建议：改成有官方文档的主机，或在文件里并列标注三个主机与各自区域。

### S3 BYOK 区域不匹配没有提示（已修）

- 现象：区域错配（国际 key 打大陆主机，或反之）返回裸 401 / 业务码 1004，
  没有任何区域提示，排查成本高。
- 实测：2026-10-04 手上这把 key 属大陆平台，`api.minimax.io` → 401，
  `api.minimaxi.com` / `api.minimax.cn` → 200。
- 建议：`config/byok.example.env` 补一行区域说明；
  `scripts/check_byok_connection.py` 可把 401/1004 归类为更明确的
  `wrong_region` 而不是笼统的 `auth_rejected`。

### S4 E1 D 组（强对照）在 harness 里只有 stub（已修）

- 原位置：`docs/engineering/offline-operator.md` §2 —— 「D 组只产生 stub」（该句已改写）
- 影响：阶段清单第 3 项要求跑 E1 的强对照 D，当前工具拿不到真实结果。
  这不是回归，是已知缺口，但它卡住了一个清单项。
- 处置：实现为**录入 + 比较**路径。D 衡量的是「换更强系统能做到什么」，自动化会毁掉对照意义，
  所以工具不执行助手，只录入真人记录并与 A/B/C/M 同形比较。见上表与 `e1_d_control.py`。

### S5 面板挂载点回退到 body，长页面上等于不可见（已修）

- 位置：`extension/src/content.js:58-61`（`ensureRoot`）、`extension/src/content.css:1-8`
- 挂载点查找顺序：`#js-pjax-container` → `main` → `document.body`。
  GitHub 新版搜索页已无 `#js-pjax-container`，回退后 `<aside>` 成为 `body` 最后一个子元素，
  即页面最末尾。CSS 的 `position: sticky; top: 12px` 救不了「元素本身在文档最底部」。
- 实测：2026-10-04 在 36 条结果的搜索页上，面板只在滚动到页面最底部才出现。
  第一次使用的人极可能判定为「功能不存在」。
- 影响：搜索结果页是产品主场景，此处不可见等于功能不可用。
- 候选修法（未决定）：改用不随改版失效的稳定锚点；或固定定位到视口内（如
  `position: fixed` 侧边栏）；或找不到锚点时明确提示而不是静默追加到 body。

### S6 `max_tokens: 256` 对推理模型过小，模型路径全程失效 ★阻塞项（已修，待真机复测）

- 位置：`extension/src/background.js:262`（`defaultModelHttp`）
- 现象：配置正确、端点探测 HTTP 200，但面板恒显示
  「模型不可用，已降级为无模型搜索」，所有候选 `来源: original_query`。
- 根因：`max_tokens: 256` 太小。MiniMax-M3 是推理模型，思考内容内联在
  `content` 的 `<think>...</think>` 里，256 token 全部消耗在思考阶段，
  JSON 尚未输出就 `finish_reason: "length"`。`parseModelExpansions`
  找不到 `{`…`}`，返回空数组 → 触发 `degrade: "model_unavailable"`。
- 实测证据（2026-10-04，真实请求）：

  | max_tokens | finish_reason | content 长度 | 去掉 think 后的 JSON |
  |---|---|---|---|
  | 256（现值） | `length` | 853（全为 think） | 无 |
  | 2048 | `stop` | 967 | 652 字节，有效 JSON |
  | 4096 | `stop` | 750 | 518 字节，有效 JSON |

- 解析器本身没问题：`shared.js:518-530` 用 `indexOf("{")` / `lastIndexOf("}")`
  截取，能处理 JSON 外面裹着散文的情况。**只需放宽 max_tokens。**
- 为什么会漏掉：选项页探测（`options.js:146`）用 `max_tokens: 8` 且只检查
  `resp.ok`，HTTP 200 就报成功，从不校验模型是否真的产出了内容。
  终端 `check_byok_connection.py` 同样只验状态码。**三处都绿，但功能是坏的。**
- 建议：至少放宽到 2048；同时让探测校验返回内容非空，否则同类问题会继续隐身。
- 附带风险：思考散文里若出现 `{` 或 `}`，`indexOf` 可能截到错误区间。
  改为显式剥离 `<think>...</think>` 更稳。

## 观察（非缺陷，供后续判断用）

### O1 降级模式下，扩展弱于 GitHub 原生搜索

2026-10-04 首次真机运行（S6 未修，模型路径全程未走）实测，查询
`剪贴板历史 管理器`：

- GitHub 原生搜索：36 条结果
- 扩展面板：5 条，`来源` 全部为 `original_query`
- 两者重合：前 4 条完全相同（`cloudxys/YouBoard`、`xinshed/clipboard-history-manager`、
  `jia209/clipboard-history`、`lang340/ClipHistory`），顺序也一致

面板的「为什么出现」字段内容是 `source=original_query; query=剪贴板历史 管理器;
original=剪贴板历史 管理器` —— 是同义反复，不是解释。

**这条不构成 H1 的任何结论**，只是一个查询的观察，且模型路径未参与。
但它提示：若 S6 修好后扩展仍只是复述原生结果，则 H1 假设需要重新审视。
判断前须有 S6 修复后的真实对照数据。

> 2026-10-05：S6 已修，**这条复测的前置条件已具备**。但复测本身仍未发生——
> 需要发起人在真机上带可用模型再跑一次同样的查询。届时应记录模型请求次数
> （不得为 0）、候选来源分布和与原生结果的重合度。

## 已排除（别再重复排查）

- `https://api.minimax.com` —— **该域名不存在**，无 A 记录，ping 报 Unknown host。
  2026-10-04 会话中曾被误当作可用主机。不是项目缺陷，是拼写问题。

## 本次已验证的环境事实（不含密钥）

| 项 | 值 |
|---|---|
| Chrome | 154.0.8037.93 |
| 扩展版本 | 0.1.3（`dist/gold-miner-extension`，与桌面副本逐字节一致） |
| 仓库 HEAD | `1ba85901eca5568e8bbc920b4afa6ef32c150506` |
| 可用主机 | `api.minimaxi.com`、`api.minimax.cn`（该 key 为大陆平台） |
| 不可用 | `api.minimax.io`（区域不匹配 401）、`api.minimax.com`（无 DNS） |
| 模型 | `MiniMax-M3`，OpenAI 兼容 `/v1/chat/completions`；**推理模型**，思考内联在 `content` 的 `<think>` 中 |
| 终端探测 | `check_byok_connection.py --live` → `ok` / HTTP 200 |
| 扩展探测 | 选项页 `http 200 ok`（仅验状态码，不验内容） |
| 面板首次真机运行 | 渲染成功，但因 S6 走降级路径，模型请求 0 次 |
| 离线套件 | `run_offline_suite.py` exit 0，Node 53/53 |

⚠️ 上表不含密钥，也不构成 E1/E2/E3 效果证据。
