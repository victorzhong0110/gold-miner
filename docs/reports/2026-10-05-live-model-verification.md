# 2026-10-05：S6 修复后的真机模型验证

承接 [S6 阻塞项修复](../session-issues.md#s6-max_tokens-256-对推理模型过小模型路径全程失效-阻塞项已修待真机复测)。
本记录是修复后**第一次真实模型请求**的证据。发起人本机 BYOK 凭据（`/tmp/byok.env`）。

**本记录不含密钥，也不构成 E1/E2/E3 任何效果证据。** 这是一次连通性与输出可用性验证，
不是评估运行：没有冻结题集、没有配平预算、没有人工判定、没有对照组。

## 环境（不含密钥）

| 项 | 值 |
|---|---|
| 端点 | `api.minimaxi.com`（区域判定：mainland） |
| 模型 | `MiniMax-M3`，OpenAI 兼容 `/v1/chat/completions`，推理模型 |
| 终端探测 | `check_byok_connection.py --live` → `ok` / HTTP 200 / `host_region: mainland` |
| 使用的代码 | `extension/src/shared.js` 真实产物（`stripReasoning` / `readModelChoice` / `parseModelExpansions`） |
| 请求体 | 与 `background.js` `defaultModelHttp` 完全一致（同一 system 提示词、同源查询） |
| 发送次数 | 6 次模型请求（1 次探测 + 5 次对比实验），无 GitHub 请求 |

## 关键结果：256 不是「一直坏」，是「不够用」

发起人 2026-10-04 记录的是 256 → `finish_reason: length`。本轮独立复现发现更准确的描述：
**256 是临界值，取决于模型这一次思考了多久，因此失败是不确定的。**

| max_tokens | finish_reason | 原 content | 剥离思考后 | 解析出的扩展 | 判定 |
|---|---|---|---|---|---|
| 256 | `length` | 899 | — | 0 | `model_output_truncated` |
| 2048 | `stop` | 1014 | 有 | 4 | 成功 |

对照同一批查询（每条各跑 256 与 2048）：

| 查询 | 256 | 2048 |
|---|---|---|
| `剪贴板历史 管理器` | `stop`，4 条扩展 | `stop`，4 条扩展 |
| `局域网内不同设备之间快速互传大文件的工具，最好支持断点续传和加密` | **`length`，0 条** | `stop`，4 条 |
| `a self-hosted offline-first diary that syncs notes between phone and desktop with end-to-end encryption` | **`length`，0 条** | `stop`，4 条 |

三条里 256 挂了两条。这比确定性失败更糟：**它表现得像「模型时好时坏」**，
而真实原因是我们的输出预算太小。修复前没有任何一处能区分这两种情况——
选项页探测只看 `resp.ok`，终端探测也只看状态码，所以三处全绿而功能是坏的。

## 修复后的模型路径确实可用

用生产代码解析真实响应（`剪贴板历史 管理器`，max_tokens 2048）：

```
http_status        200
max_tokens sent    2048
finish_reason      stop
raw content chars  1153      ← 含 <think>
after strip chars  472
had <think> block  true
expansions parsed  4
   - zh | 剪贴板历史 管理器
   - zh | 剪贴板管理工具
   - en | clipboard history manager
   - en | clipboard manager
```

`<think>` 被显式剥离，JSON 正常解析，中英各产出扩展。
**这是连通性与输出可用性证据，不是 H1 增益证据**：单次运行、无对照组、无人工判定。

## 这改变了什么，没改变什么

**已成立**：模型路径不再是「从未真正运行」。发起人 2026-10-04 观察到的
「候选来源全部 `original_query`」「模型请求 0 次」在修复后不再必然发生。

**仍未发生**：O1 的复测（降级模式下扩展是否只是复述 GitHub 原生结果）仍需发起人
在真机上带可用模型重跑原查询，并记录模型请求次数、来源分布、与原生结果的重合度。
E1 B/C/M/D 实测、真人盲判、E2 会话、E3 对照、E7 一周日记全部未变，仍按
`pending-human` / `pending-live` / `pending-time` 记。

**本轮结论只到「模型路径可用」为止。** 扩展是否比 GitHub 原生搜索更有用，
仍然没有任何证据支持或反对。
