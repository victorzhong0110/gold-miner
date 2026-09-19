# E5 本地复用脚手架（未跑第二环境）

扩展选项页可导出 / 导入 `gold-miner-cache-v1`。清洗规则在 `extension/src/shared.js` 的 `sanitizeExport`：

- 去掉 `apiKey` / token / 私有备注
- 去掉 `private: true` 或名字像私有的仓库
- 只保留 repo、purpose、source、language、content_version、processing_mode

实验步骤（**未运行**）：

1. 浏览器 A 导出。
2. 浏览器 B 导入后打开同一公开仓库页，看是否少一次搜索。
3. 改 README 后 `content_version` 应变，旧缓存不得冒充当前页。

共享包不得含密钥、私人笔记、私有仓库。本目录不存放真实导出文件。
