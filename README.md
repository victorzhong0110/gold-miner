# 黄金矿工 Gold Miner

跨语言 GitHub 项目发现与自然探索。用你自己的语言发现、阅读、继续探索 GitHub 上的项目；首轮中英双向。

[English](README.en.md)

**当前状态：产品规划阶段，尚无可安装的扩展版本，也没有效果结论。** 已完成的是 v0.3 计划、一份设计研究记录、一次计划评审，以及项目自身可发现性的首次探测（E8）。

## 这个仓库里有什么

- [产品验证与开发计划 v0.3](docs/plan/v0.3.md)：已确认需求、四个验收场景、发现系统的问题、翻译复用与费用边界、实验 E1–E8、命题 H1–H8、分阶段开发、MiniMax 接入核对。v0.1、v0.2 未入库。
- [2026-09-17 计划评审](docs/reviews/2026-09-17-v0.3-review.md)：对 v0.3 的逐项评审、带证据的发现、建议进入 v0.4 的改动。开发前先读这一篇。
- 决策记录：[0001 项目名称](docs/decisions/0001-project-name.md)（待决策）、[0002 模型接入配置](docs/decisions/0002-model-endpoint-config.md)（建议）、[0003 许可证](docs/decisions/0003-license.md)（待决策）。
- [工程前置检查](docs/engineering/prerequisites.md)：GitHub Search API 配额、中文查询实测、GitHub 页面导航、扩展架构与密钥边界。写扩展代码前逐项过。
- 实验：[E1 跨语言搜索协议](experiments/E1-cross-language-search/protocol.md) 与 [预注册查询集](experiments/E1-cross-language-search/queries.yaml)；[E8 可发现性探测记录](experiments/E8-discoverability/2026-09-17-probe.md) 与 [记录模板](experiments/E8-discoverability/template.md)。
- [待办与 issue 草稿](docs/backlog.md)：H1–H8、E1–E9 与仓库整理项，可直接开成 issues。
- [设计参考：EhViewer 对跨语言检索的启发](docs/research/ehviewer-cross-language-search.md)：来源核对、多语言软件术语表、复用边界，以及词表／AI／混合方案实验 E9。

## 下一步（按顺序）

1. 决定项目名称（[0001](docs/decisions/0001-project-name.md)）。当前名称在 GitHub 搜索中被 [xitu/gold-miner](https://github.com/xitu/gold-miner) 与黄金矿工游戏占满，见 [E8 探测](experiments/E8-discoverability/2026-09-17-probe.md)。
2. 补齐仓库简介、topics、许可证与英文 README（本文件已配英文版）。
3. 先用脚本验证 H1（语言是否造成遗漏），不先写扩展。协议见 [E1](experiments/E1-cross-language-search/protocol.md)。
4. H1 有增益再进入扩展开发；先过 [工程前置检查](docs/engineering/prerequisites.md)。

## 边界

源码开源；模型调用使用使用者自己的 API，项目不为他人使用付费，也不提供公共推理服务。发起人先自用，再决定是否推广。
