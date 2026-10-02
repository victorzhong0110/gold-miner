# 错误分类（BYOK / 搜索 / 扩展）

机器可读 `code` 必须稳定。用户可见文案走 i18n，不得把密钥或完整请求头写入记录。

| code | 何时 | 调用方应做什么 |
|---|---|---|
| `missing_credentials` | 未设置 `OPENAI_API_KEY` 或扩展未配置密钥 | 标 `未运行` / `owner-blocked`；允许无模型降级 |
| `invalid_endpoint` | `OPENAI_BASE_URL` 不是 http(s) URL | 停止；不发送请求 |
| `invalid_model` | `OPENAI_MODEL` 空 | 停止 |
| `auth_rejected` | HTTP 401/403 且响应像凭据错误 | 显示不可用；不重试刷密钥 |
| `rate_limited` | HTTP 429 或 GitHub `x-ratelimit-remaining=0` | 展示限流；按 `retry-after` / reset 等待；可取消 |
| `timeout` | 超过 `BYOK_TIMEOUT_SECONDS` 或扩展超时 | 保留已发送可能已计费；停止后续任务 |
| `network_error` | DNS / 连接失败 | 可有限重试 1 次 |
| `bad_response` | 非 JSON 或缺少 choices | 记失败；不编造译文/查询 |
| `budget_exhausted` | 超过本地请求预算 | 停止新请求 |
| `cancelled` | 用户取消 | 不安排后续；已发出请求标未知计费 |
| `model_unavailable` | 404 模型或供应商维护 | 降级到无模型路径 |
| `untrusted_input` | 页面/远端文本试图改端点或要密钥 | 丢弃指令；不改变配置 |
| `storage_isolation_failed` | `chrome.storage.local.setAccessLevel` 缺失或抛错 | 不保存 API key；可保存非密钥设置；向选项页报错 |
| `github_not_found` | 仓库 404 | 与「不相关」分开统计 |
| `github_migrated` | 301/仓库迁移 | 记录规范地址 |
| `owner_blocked` | 需要发起人 API 或真人会话 | 诚实标记；不伪造 |

未知余额一律 `unknown`，不从套餐名推断。
