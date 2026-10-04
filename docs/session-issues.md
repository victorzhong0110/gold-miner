# 会话问题清单

发起人真机操作中遇到的问题，逐条记录，等证据齐了批量修。
维护者：Mavis。首次记录 2026-10-04（第 1、2 项执行期间）。

与 `docs/backlog.md`（工作包）、`docs/known-limitations.md`（产品限制）不重复：
这里只放**真机操作暴露出来的问题**，修完应回流到上面两份之一。

## 修复状态（2026-10-04）

S1/S3/S5/S6 已在0.1.4源码修复并通过离线回归，11项Chromium fixture验收全部通过（docs/reports/browser-acceptance-2026-10-04.json）；真人修复后复测未运行。S2最新官方大陆文档已列api.minimax.cn，保留默认值并补区域/来源说明。S4的工具、模型和预算已由发起人在2026-10-04决定（docs/decisions/0004-minimax-d-group.md）：MiniMax-M3，不设任务条数上限。实跑未发生：本执行环境没有 `MINIMAX_API_KEY`、`OPENAI_API_KEY`、`GITHUB_TOKEN`，模型请求 0，没有创建 `runs/` 目录，没有候选。见 docs/reports/2026-10-04-e1-d-not-run.json。下文原始观察保留供追溯。

| 编号 | 处理 | 验证范围 |
|---|---|---|
| S1 | 读取当前输入、输入变化取消探测、忽略迟到响应、显示实际主机/模型；探测不保存输入 | 选项页回归及新增Chromium fixture |
| S2 | 已核对2026-10-04官方大陆文档列.cn；示例补官方链接和国际/大陆说明 | 官方文档核对，不重做个人密钥测试 |
| S3 | HTTP401/403或业务1004保留auth_rejected，提示核对密钥和区域；不武断判断wrong_region | JS/Python模拟响应 |
| S4 | 工具/模型/预算已决定为 MiniMax-M3、跑满 eval.batch_1。实跑未发生：执行环境没有密钥，模型请求 0 | 未运行。缺密钥，不是「尚未选定工具」 |
| S5 | 固定在视口内，限制宽高并允许面板内滚动；原有关闭/取消保留 | 无main、6000px长页浏览器fixture |
| S6 | 工作请求及两个探测均2048token；剥离think、拒绝length/空答案；探测要求pong | HTTP路径与解析回归；没有调用真实模型 |

## 原始问题记录

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

### S2 `config/byok.example.env` 默认主机不在官方文档

- 位置：`config/byok.example.env:5`
- 现状：默认 `https://api.minimax.cn/v1`。MiniMax 官方文档列出的是
  `https://api.minimax.io/v1`（国际）与 `https://api.minimaxi.com/v1`（大陆）。
  `.cn` 实测可用（HTTP 200），但官方文档未列。
- 建议：改成有官方文档的主机，或在文件里并列标注三个主机与各自区域。

### S3 BYOK 区域不匹配没有提示

- 现象：区域错配（国际 key 打大陆主机，或反之）返回裸 401 / 业务码 1004，
  没有任何区域提示，排查成本高。
- 实测：2026-10-04 手上这把 key 属大陆平台，`api.minimax.io` → 401，
  `api.minimaxi.com` / `api.minimax.cn` → 200。
- 建议：`config/byok.example.env` 补一行区域说明；
  `scripts/check_byok_connection.py` 可把 401/1004 归类为更明确的
  `wrong_region` 而不是笼统的 `auth_rejected`。

### S4 E1 D 组（强对照）在 harness 里只有 stub

- 位置：`docs/engineering/offline-operator.md` §2 —— 「D 组只产生 stub：`blocked` / `未运行`」
- 影响：阶段清单第 3 项要求跑 E1 的强对照 D，当前工具拿不到真实结果。
  这不是回归，是已知缺口，但它卡住了一个清单项。
- 需要决定：实现 D 组，还是明确写「本阶段不授权 D」。

### S5 面板挂载点回退到 body，长页面上等于不可见

- 位置：`extension/src/content.js:58-61`（`ensureRoot`）、`extension/src/content.css:1-8`
- 挂载点查找顺序：`#js-pjax-container` → `main` → `document.body`。
  GitHub 新版搜索页已无 `#js-pjax-container`，回退后 `<aside>` 成为 `body` 最后一个子元素，
  即页面最末尾。CSS 的 `position: sticky; top: 12px` 救不了「元素本身在文档最底部」。
- 实测：2026-10-04 在 36 条结果的搜索页上，面板只在滚动到页面最底部才出现。
  第一次使用的人极可能判定为「功能不存在」。
- 影响：搜索结果页是产品主场景，此处不可见等于功能不可用。
- 候选修法（未决定）：改用不随改版失效的稳定锚点；或固定定位到视口内（如
  `position: fixed` 侧边栏）；或找不到锚点时明确提示而不是静默追加到 body。

### S6 `max_tokens: 256` 对推理模型过小，模型路径全程失效 ★阻塞项

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
