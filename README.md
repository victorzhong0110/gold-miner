# 黄金矿工 Gold Miner

跨语言 GitHub 项目发现与自然探索。用自己的语言发现、阅读、继续探索值得使用或学习的开源项目；首轮中英双向，计划以 Chrome 扩展在 GitHub 原页面内工作。

[English](README.en.md)

**当前处于产品验证规划阶段，尚无可安装扩展，也没有产品效果结论。** 本轮更新了 v0.4 行动计划、讨论来源、E1 搜索协议与 E2 无目标发现协议。尚未运行这两项实验或调用个人模型 API。

## 从这里开始

- [完整行动计划 v0.4](docs/plan/v0.4.md)：目标与约束、现在可做的工作包、条件满足后再做的工作、全部实验、工期、待定事项与暂停条件。
- [自动翻译与推荐：讨论及想法来源](docs/research/2026-09-17-translation-and-discovery.md)：被通用 AI 替代的风险、TikTok 机制借鉴、语言障碍与兴趣反馈、共享发现条目，以及对 Claude 评审的处理。
- [当前待办](docs/backlog.md)：执行顺序、状态和依赖；未创建对应 GitHub issues。

## 下一步

1. 固定阅读对照与独立评估材料，检查真实候选来源。
2. 用小脚本比较原生搜索、简单译词、跨语言扩展与同语言等预算扩展。
3. 在同样好的翻译条件下，比较照常浏览和少量辅助推荐；先人工探索候选价值，再检验自动方法。
4. 根据两条路径的实际证据选择最小扩展范围；随后验证安装、配置、费用、自然度和复用。

工作名沿用黄金矿工 / Gold Miner。名称竞争需要继续检查，改名不作为实验前置条件。搜索和无目标发现分别判断；中文 README 的比例不决定项目是否继续。

## 协议与参考

- [E1 跨语言搜索](experiments/E1-cross-language-search/protocol.md)；[任务文件](experiments/E1-cross-language-search/queries.yaml)目前只有开发题，评估批次尚未冻结。
- [E2 无目标发现](experiments/E2-open-ended-discovery/protocol.md)；完整自然度随后由 E4 验证。
- [工程检查](docs/engineering/prerequisites.md)；[模型配置方案](docs/decisions/0002-model-endpoint-config.md)。
- [E8 首次探测](experiments/E8-discoverability/2026-09-17-probe.md)与[后续模板](experiments/E8-discoverability/template.md)。
- [名称记录与元数据文案](docs/decisions/0001-project-name.md)；[许可证备选](docs/decisions/0003-license.md)，具体许可证尚未落地。
- [EhViewer 研究](docs/research/ehviewer-cross-language-search.md)：概念映射与词表启发，包含代码和数据的复用边界。
- 历史：[v0.3](docs/plan/v0.3.md)、[Claude 评审](docs/reviews/2026-09-17-v0.3-review.md)。它们保留原文；当前执行顺序以 v0.4 为准。

## 边界

源码计划开源，短期不以盈利为目的。模型调用由使用者自备 API，项目不承担公共推理费用。个人偏好优先本地保存，贡献共享内容需主动启用；没有共享译文的项目仍须有发现路径。

先采用现成翻译作为强对照，仅为真实缺口补充能力。独立发现网站、全量爬取、大型推荐模型和公共模型代理不在首轮范围。
