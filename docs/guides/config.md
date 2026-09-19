# 配置说明

## 环境变量（脚本）

见 `config/byok.example.env`。使用 `GITHUB_TOKEN`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_API_KEY`。不要把填好的文件提交进仓库。

探测：`python3 scripts/check_byok_connection.py`（默认不发请求）。加 `--live` 才发一次小请求。

## 扩展 BYOK

在选项页填写同一组字段。密钥进 `chrome.storage.local`，并由 service worker 尝试设为仅受信上下文可读。内容脚本只收到 `hasModel` 布尔值。

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
