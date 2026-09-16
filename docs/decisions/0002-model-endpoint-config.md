# 0002 模型接入配置

状态：建议（发起人确认后生效）  
提出日期：2026-09-17  
影响范围：v0.3 第 8 节、第 7 节技术方案、第 4 节费用边界

## 背景

v0.3 第 8 节以 MiniMax Token Plan Starter 为唯一接入对象。端点核对无误（2026-09-17 复核官方"其他工具"页：OpenAI 兼容 `https://api.minimax.cn/v1`，Anthropic 兼容 `https://api.minimax.cn/anthropic`，模型 `MiniMax-M3`，订阅 Key 前缀 `sk-cp-`）。但产品原则是"使用者自备 API"，把单一供应商写进方案会让每个试用者都被迫开同一家账号，也让费用与额度显示逻辑绑死一家。

## 决定

扩展的模型配置是一个供应商无关的三元组加协议标记：

```
provider_preset: string | "custom"     # 仅用于预填与用量查询适配
protocol:        "openai" | "anthropic"
base_url:        string                # 例 https://api.minimax.cn/v1
model:           string                # 例 MiniMax-M3
api_key:         string                # 仅存 chrome.storage.local，不进 sync、日志、译文包、研究记录
```

预设只是预填这几个字段，不改变数据流：

- MiniMax 中国站 Token Plan：`openai` / `https://api.minimax.cn/v1` / `MiniMax-M3`。发起人的首个实例。
- DeepSeek、OpenAI 及其他 OpenAI 兼容服务：用户填 base_url 与 model。
- Ollama 本地：`openai` / `http://localhost:11434/v1` / 用户本地模型名。让试用者真正零费用；Ollama 对浏览器来源有校验，扩展请求可能需要用户设置 `OLLAMA_ORIGINS` 放行扩展来源，需在第 1b 阶段实测并写进安装说明。

## 实施要求

- 请求只从 service worker 发出，content script 不持有密钥，也不直接请求模型端点。
- 主机权限：`github.com`、`api.github.com` 为固定权限；模型端点使用 MV3 `optional_host_permissions`，在用户保存配置时按 base_url 的 origin 动态申请，不预申请全网权限。
- 用量显示：只有预设明确提供用量接口时才显示余额与窗口；`custom` 与未知情况显示"未知"，并按本地计数器显示本次会话的请求数、失败数与估算 token 数。这与 v0.3 第 8 节"无法识别额度时显示未知"一致。
- 预算控制（v0.3 第 4 节）供应商无关地实现：每页面请求上限、任务合并、并发上限 2、重试上限 2 加退避、AbortController 取消、可暂停自动生成。
- 首次连接检查：保存配置后用一段固定公开文本发一次最小请求，记录模型名回显、延迟、返回格式；失败时给出协议／地址／密钥三类可区分的错误提示。

## 后果

- v0.3 第 8 节改题为"模型接入配置"，MiniMax 内容降为"首个预设的核对记录"。
- 密钥类型说明（订阅 Key 与按量 Key 不是同一额度）保留在 MiniMax 预设的帮助文本里，不出现在通用配置界面。
- 测试用例增加：切换预设不残留旧密钥；导出译文包与研究记录时不含 `api_key` 与 `base_url` 中的凭据片段。
