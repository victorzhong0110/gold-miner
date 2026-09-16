# EhViewer 对黄金矿工跨语言检索的启发

记录日期：2026-09-16  
状态：研究记录与待验证方案，尚未实现或开展对照实验。

## 想法来源

项目发起人提供了 [seven332/EhViewer](https://github.com/seven332/EhViewer)，并提出“其中的跨语言检索能力能否复用”。据此检查了原仓库的 `master` 与 `tag-translations` 分支。

核心启发是：用户看到熟悉语言的名称，系统保留原始标签作为操作依据；翻译数据共享发布，客户端在本地复用。由此提出黄金矿工自己的多语言软件术语表，以及“词表优先、必要时使用个人 AI”的候选方案。

下面明确区分已观察到的实现与我们提出的扩展。此记录只针对所链接的原仓库，不代表其他 EhViewer 分支的能力。

## 在原仓库中观察到什么

| 观察 | 源码依据 |
| --- | --- |
| 标签展示时查找译文，没有译文则显示原标签；控件另外保存原始命名空间和标签，点击时使用原始值检索。 | [GalleryDetailScene.java](https://github.com/seven332/EhViewer/blob/master/app/src/main/java/com/hippo/ehviewer/ui/scene/GalleryDetailScene.java)，标签绑定与点击处理 |
| 标签词库下载后保存在本地，按原标签查译文；更新时比较校验值，下载并检查新数据。 | [EhTagDatabase.java](https://github.com/seven332/EhViewer/blob/master/app/src/main/java/com/hippo/ehviewer/client/EhTagDatabase.java) |
| 简体中文资源指定独立词库与校验文件的下载地址。 | [arrays.xml](https://github.com/seven332/EhViewer/blob/master/app/src/main/res/values-zh-rCN/arrays.xml) |
| 构建脚本从 EhTagTranslator 的 Wiki Markdown 表格提取原标签和译文，生成排序数据与校验文件。 | [tag-translations/main.py](https://github.com/seven332/EhViewer/blob/tag-translations/main.py) |
| 检查到的普通输入链路将用户查询传给 URL 构造器，构造搜索参数；没有在该链路看到通用的查询翻译或语义检索。 | [SearchLayout.java](https://github.com/seven332/EhViewer/blob/master/app/src/main/java/com/hippo/ehviewer/widget/SearchLayout.java)、[ListUrlBuilder.java](https://github.com/seven332/EhViewer/blob/master/app/src/main/java/com/hippo/ehviewer/client/data/ListUrlBuilder.java) |

因此，已确认的参考能力是本地标签翻译、显示与原始标识分离、共享词库更新。不能由此声称它已经解决任意自然语言需求的跨语言搜索。对“输入中文自动联想英文标签”的具体体验，如后续需要复用，应先定位对应分支和版本。

原仓库 README 标注为 DEPRECATED，仓库已归档。这里把它作为设计参考，不把它作为正在维护的通用检索依赖。

## 黄金矿工可以借鉴的设计

### 用多语言表达关联同一个用途概念

建立属于开源软件领域的小型术语表。每个概念保存稳定标识、中英文名称、常见别名和可用于查询的表达，例如：

| 概念标识示例 | 中文表达示例 | 英文表达示例 |
| --- | --- | --- |
| clipboard-history | 剪贴板历史、剪贴板记录 | clipboard history |
| self-hosting | 自托管、自部署 | self-hosted, self-hosting |
| optical-character-recognition | 光学字符识别、文字识别 | OCR, optical character recognition |

这些是待验证的映射示例，不是准确率结论。“自托管”不自动意味着“离线可用”；同义词、相关词和使用条件需要区分。存在多义时保留候选解释，不能用一个固定译词静默覆盖用户意图。

术语表支持按中文或英文名称、别名反向查概念，再生成多语言查询。这是我们新增的设计，不是上述原仓库已经验证的功能。

### 本地词表优先 个人 AI 补充

常见且明确的表达可以在本地解析；未覆盖的词、长句和有歧义的条件，再按用户的调用设置使用个人 API。查询改写结果可以缓存，避免重复消耗。

这是一项待比较的方案，不预设词表一定更省或更准。词表命中也不意味着理解了整句需求，不能因此跳过否定、部署条件和上下文。

### 共享数据与实际检索分开

词表以可版本化的数据文件维护，用户可贡献别名与纠错，客户端缓存并检查更新。可借鉴 EhViewer 的发布与本地复用方式，但不必照搬其 Android 代码、二进制格式或旧校验方案。

词表用于生成查询和辅助理解，不是仓库白名单。仍需获取真实中英文候选、搜索必要的 README 内容、合并去重和核对用途。没有词条、没有规范 topics、没有共享译文的仓库，也必须保留发现路径。

这种映射还可辅助把兴趣选项显示成用户的语言，但不能单独解决无目标推荐质量、README 翻译或项目是否值得使用的问题。

## 复用边界与来源许可

- **实现代码**：原仓库采用 [Apache License 2.0](https://github.com/seven332/EhViewer/blob/master/LICENSE)。如实际移植，需要保留适用许可、版权与 NOTICE，并标明修改；本轮未复制其实现。
- **标签数据**：翻译分支 [README](https://github.com/seven332/EhViewer/blob/tag-translations/README.md) 明确说明词库修改自 [EhTagTranslator](https://github.com/Mapaler/EhTagTranslator)，采用 CC BY-NC-SA 3.0。不能把代码许可视为数据许可。
- **领域适配**：原词库面向原站内容标签，与开源软件用途不匹配。建议独立维护软件术语表，不直接导入其词库。我们短期不盈利也不消除数据许可条件。
- **工程适配**：黄金矿工目标是 Chrome 扩展。优先参考交互和数据组织方式，具体实现采用适合扩展的技术；是否移植小段代码，待实现时再判断。

## 拟补充实验 E9

问题：词表能否在不明显损害发现效果的前提下，减少模型调用并缩短等待？

| 组别 | 查询处理方式 |
| --- | --- |
| A 纯词表 | 原始查询加本地多语言映射，不调用模型；未覆盖情况明确记录。 |
| B 纯 AI | 使用相同模型与固定提示词生成查询，不使用术语表。 |
| C 词表加 AI | 先查词表，在未覆盖或存在歧义时调用同一模型补充。 |

三组保留相同的原始查询路径、数据来源、结果排序方式、查询数量上限和候选检查预算。记录实际请求数；缓存冷启动与已有缓存分别观察，避免把缓存收益误算成词表理解能力。

开发题与评估题分开，覆盖中英文双向、高频术语、未收录词、多义词、否定条件和较长需求。不能只挑术语表已有词条作为评估题。

记录以下结果：

- 用户认为适合且值得继续看的真实仓库，以及各方法独有的好结果。
- 不相关结果、硬条件误判、未覆盖词和歧义处理错误。
- 模型调用、实际用量与等待时间，以及词表维护和纠错负担。
- 用户是否需要自己换语言、修正查询或理解额外选项。

如果混合方案节省调用却漏掉关键项目，应调整触发条件或回退策略；如果简单词表已经足够，则减少模型参与。这个实验补充现有计划，不替代跨语言搜索 E1、无目标发现 E2 和自然度 E4。

## 当前结论与下一步

记录为候选设计：先做一份小型、可追溯来源的软件术语表，再比较三种方式。当前没有实现、性能数据或用户效果结论，也没有把 EhViewer 的词库或代码纳入黄金矿工。

本次参考范围是源码阅读，未运行 EhViewer，也未验证其历史下载地址目前是否可用。后续实现前，应固定参考提交版本并复核实际采用部分的许可与依赖。
