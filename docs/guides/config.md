# 配置说明

## 环境变量（脚本）

见 `config/byok.example.env`。使用 `GITHUB_TOKEN`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_API_KEY`。不要把填好的文件提交进仓库。

探测：`python3 scripts/check_byok_connection.py`（默认不发请求）。加 `--live` 才发一次小请求。

## 扩展 BYOK

在选项页填写同一组字段。密钥只经 service worker 的 `SAVE_SETTINGS` 写入，且必须先成功调用 `chrome.storage.local.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" })`。隔离失败则密钥不保存（语言/兴趣仍可保存）。内容脚本只收到 `hasModel`：该布尔值表示**本次结果是否真正走过模型路径**，不是「是否填了密钥」。

未配置模型时扩展仍可：

- 保留原始查询
- 用内置词表做有限跨语言扩展（不是模型 C 组）
- 调用公开 GitHub Search
- 按兴趣/反馈做规则排序

额度显示为未知，除非你自己在供应商控制台查看。

## 个性化

- 默认：兴趣 + 当前页面。
- 浏览历史：默认关，需勾选。
- 可关个性化或清除 seen/feedback/cache。
- 反馈「不相关 / 见过」会影响后续排序，并保留探索余量，避免只剩同一类。

## 0.1.3 端点与缓存

保存 BYOK 配置时会申请指定端点权限；拒绝权限就不保存配置。端点仅允许 HTTPS 或本机 `http://127.0.0.1`，不得含 URL 用户名、密码、查询或片段；认证请求拒绝重定向，12 秒超时。

模型或密钥配置变化后重新尝试模型，不复用旧 rules 结果阻止恢复。缓存按内容指纹、语言、模式和查询区分，24 小时过期，最多 100 条；旧版本没有时间戳的缓存不命中。导入模型结果不冒充本机已验证的模型配置。

可选历史当前仅记录在本机，没有用于推荐排序；兴趣、当前仓库和显式反馈用于推荐。项目未宣称 stars 历史接入。

## 0.1.4 探测与区域

探测使用当前输入（无需先保存），显示实际主机/模型；修改输入立即使旧结果失效。探测不保存密钥，只有保存按钮会保存设置。HTTP200必须同时有最终pong答案才成功；空答案、仅think或length会显示失败，成功仅说明连接和最小输出，不保证检索JSON成功。工作请求和探测最多2048输出token（含推理），不自动重试；探测可能计费。

MiniMax国际文档：https://platform.minimax.io/docs/api-reference/text-openai-api（api.minimax.io/v1）；大陆现行文档：https://platform.minimax.cn/docs/api-reference/text-openai-api（api.minimax.cn/v1）。api.minimaxi.com为本次用户已验证的旧入口。选择注册平台控制台给出的端点；鉴权拒绝时检查区域及密钥有效性，不能单凭401断定区域错配。
