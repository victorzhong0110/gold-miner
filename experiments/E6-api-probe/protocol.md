# E6 个人模型最小请求协议（W6，2026-09-22）

本文件是本包自己的协议。它不改 E1 协议第 7 节：一次连通或一次失败不决定搜索、推荐或翻译范围，也不把费用数字写成产品成功证明。未知用量保持未知，不从套餐名称推断额度。

对应：`docs/decisions/0002-model-endpoint-config.md`、`docs/engineering/prerequisites.md` 第 2 节、`docs/plan/v0.4.md` 第 5 节 E6 行。

## 何时发送

仅当 `OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_API_KEY` 三个环境变量都有值，且 `request_budget` 为 1，且发送前未取消，才发一次请求。缺任一项时状态为未运行，`actual_requests` 为 0，不调用 HTTP。

请求体是 OpenAI 聊天补全：一条公开提示 `Reply with the single word pong.`，`max_tokens` 不超过 32。不翻译整个仓库。不自动重试，避免重复计费。取消只在 `http_post` 之前生效。一旦调用 `http_post`，即使异常也记 `sent_requests=1`，并写明已发送请求可能已计费。

## 记录字段

一行 JSONL：

- 身份与时间：`run_id`、`started_at`、`finished_at`、`elapsed_ms`
- 配置是否存在：四个布尔值，只表示变量有没有设，不写变量内容
- 目标：`model`、`base_url`（去掉用户信息与查询串）、`protocol`
- 预算：`request_budget`、`max_output_tokens`、`actual_requests`、`sent_requests`、`retries`、`cancelled_before_send`、`cache_hits`
- 结果：`status`、`http_status`、`response_format`、`visible_response_id`、`model_output`
- 用量：`usage_prompt_tokens`、`usage_completion_tokens`、`usage_total_tokens`
- 失败：`error_class`、`error_detail`、`billing_note`

`status`：`未运行`、`已运行`、`取消`、`失败`。

`error_class`：`无`、`未配置`、`预算`、`取消`、`地址`、`协议`、`权限或凭据`、`额度`、`限流`、`网络`、`响应格式`。

未发送时 `elapsed_ms` 与三项用量都是 `未知`，`model_output` 是 `未运行`。响应里没有 usage 对象时，用量保持 `未知`，不补 0。HTTP 429 只有在正文出现 quota、billing 或 insufficient_quota 时记为额度，否则记限流。

密钥、`Authorization` 头和 `Bearer` 不进入记录。若输出里回显密钥，替换为 `[redacted]`；替换后仍包含原密钥则拒绝写出。
