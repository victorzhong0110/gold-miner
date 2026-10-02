# 黄金矿工 Gold Miner

在 GitHub 原页面里，用自己的语言发现值得使用或学习的开源项目。Chrome MV3 试验扩展支持中英搜索、仓库页探索、兴趣与反馈、本地缓存复用；模型 API 由使用者自备。

[English](README.en.md) · [10 分钟上手](docs/guides/getting-started.md) · [45 项工作包状态](docs/work-packages/STATUS.md)

**当前版本 0.1.3，工程试验包。** 267 项 Python、53 项扩展回归通过；0.1.3 的新增并发浏览器验收待 CI。此前 [0.1.2 的8项 Chromium fixture 验收](docs/reports/browser-acceptance-2026-10-02.json) 已通过；本人 Chrome 安装、跨语言增益、真人探索和持续使用尚未验收。已有 A 组搜索、README 字段配对及六条 gtx 翻译记录，不能由它们推出产品有效。

## 使用

1. 克隆本仓库，或解压 [0.1.3 试验包](dist/gold-miner-extension-0.1.3.zip)。
2. 在 `chrome://extensions` 开启开发者模式，加载 `extension/` 或解压后的目录。Chrome 102 及以上。
3. 打开 GitHub 搜索或仓库页。点击扩展图标进入设置，选择阅读语言和兴趣。
4. 可选配置自己的 OpenAI 兼容 API 端点、模型和密钥，并授权该端点。留空时使用有限词表和公开搜索。

取消和关闭会停止后续请求；已发出的模型调用可能计费。个人偏好和密钥留在本机，导出包不含密钥。自有代码与文档采用 [MIT](LICENSE)，外部材料见 [第三方声明](THIRD_PARTY_NOTICES.md)，尚未发布商店版本。

## 开发与验证

```bash
python3 scripts/run_offline_suite.py
bash extension/scripts/build.sh
```

构建产物与源码逐文件比对；`dist/build-manifest.json` 记录源码 SHA 和 ZIP 哈希。E1 生成→检索桥见 `experiments/E1-cross-language-search/scripts/e1_pipeline.py`；盲判遮蔽与回填见同目录 `blind_eval.py`。普通测试不请求付费 API。

## 项目资料

- [阶段报告与未完成项](docs/reports/2026-10-02-phase-review.md)
- [完整 WP1–WP6 任务定义](docs/work-packages/README.md)，覆盖 W0–W14、E1–E9。
- [E1 搜索协议](experiments/E1-cross-language-search/protocol.md) · [E2 探索协议](experiments/E2-open-ended-discovery/protocol.md)
- [配置](docs/guides/config.md) · [实验操作](docs/engineering/offline-operator.md)
- [讨论来源与产品思考](docs/research/2026-09-17-translation-and-discovery.md) · [EhViewer 研究来源](docs/research/ehviewer-cross-language-search.md)
- [名称记录](docs/decisions/0001-project-name.md) · [许可决定](docs/decisions/0003-license.md)
- 历史计划：[v0.3](docs/plan/v0.3.md)、[v0.4](docs/plan/v0.4.md)、[v0.5](docs/plan/v0.5-compressed-wp.md)。

项目不提供公共模型代理或推理补贴。不设 stars 排除下限；先使用现成翻译，是否补充翻译能力由真实缺口决定。独立网站、全量 GitHub 抓取和大型推荐模型不在本阶段范围。

需要发起人完成的配置、实际体验和判断见 [本阶段操作清单](docs/guides/owner-stage-checklist.md)。

E2 完整会话/候选记录见 [记录说明](experiments/E2-open-ended-discovery/recording.md)，验证命令支持 session、candidate、diary 和 discovery，不代填真人结果。
