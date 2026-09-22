# E8 复测材料 2026-09-22（未运行）

对应 [v0.4](../../docs/plan/v0.4.md) 的 W7、[模板](template.md)、[决策 0001](../../docs/decisions/0001-project-name.md)、[决策 0003](../../docs/decisions/0003-license.md)。

性质：准备包。双语简介和 topics 只写在 [metadata-draft.json](metadata-draft.json)，入口查询写在 [entry-queries.jsonl](entry-queries.jsonl)，许可证备选写在 [license-options.md](license-options.md)。没有把这些字段写进 GitHub 仓库设置，没有改仓库名，没有添加 `LICENSE`。

本文件不覆盖 [2026-09-17 基线](2026-09-17-probe.md)，也不改写 [2026-09-18 的 403 记录](2026-09-18-retest.md)。那次记录仍是「读元数据即限流、搜索未发起」，不是新的排名。

## 条件

- 日期：2026-09-22。这是材料准备日期，不是请求时间。时区：准备说明使用 UTC 日期；没有请求，因此没有响应时间。
- 批次：prep-01。操作：只准备，不搜索。
- 仓库名：`victorzhong0110/gold-miner`。未改名。
- 简介 / topics：草案未应用。`applied_to_github` 为 false。
- 远程 description、topics、license、README 版本：未运行。不得把 9 月 17 日的空简介当作今天的远程状态。
- 许可证：待决策。决策 0001、0003 仍是待决策。
- 是否刚改过 GitHub 上的这些字段：否。
- 入口：GitHub REST API、GitHub 网页、普通搜索引擎的查询都已固定，执行状态都是未运行。
- 认证、登录、界面语言、地区：未检查。
- 查看窗口：拟定前 20 条。窗口还没有被实际结果填上。
- 实际用户的自然说法：未收集。查询来自模板示例和 9 月 17 日探测原文，不是新的用户原话。

## 查询

三组入口，外加单独名称诊断，以及 9 月 17 日那些带「GitHub」一词的站内查询。后一组只为以后对照旧记录，站内搜索会把这个词当成普通词项，不是「限定在 GitHub」的指令。

| 角色 | 入口 | 查询 |
|---|---|---|
| 入口，名称加用途 / 纯用途 | GitHub REST、GitHub 网页 | 站内去掉「GitHub」：`黄金矿工 跨语言`；`Gold Miner discovery`；`跨语言 项目发现`；`cross-language project discovery` |
| 入口，名称加用途 / 纯用途 | 普通搜索引擎 | 保留「GitHub」：`黄金矿工 GitHub`；`Gold Miner GitHub discovery`；`GitHub 跨语言搜索`；`GitHub project discovery across languages` |
| 诊断，单独名称 | GitHub REST、GitHub 网页 | `黄金矿工`；`gold miner`。不要求裸名称排第一 |
| 诊断，限定字段 | GitHub REST | `gold-miner in:name`。这是诊断语法，不是默认搜索验收 |
| 基线变体 | GitHub REST | 9 月 17 日六条带「GitHub」的站内查询，见 JSONL 里 `role=baseline_variant` |

每条的语言、窗口、来源和 `status` 以 JSONL 为准。全部 `status` 为「未运行」，`result` 为 null。

## 每条结果

未运行。没有可见总数，没有前若干名，没有官方仓库位置。未运行不是「在本次窗口内未找到」，也不是零结果。没有限流记录，因为没有发出请求。

## 解读

下面这些只能留到真正复测之后。本文件不回答：

- 名称加用途能否定位官方入口：未运行。
- 只知道用途时能否发现本项目：未运行。
- 相对 9 月 17 日，变的是名称、元数据、收录时间还是入口：未运行。草案还没应用，不能把草案当成已经改变的元数据。
- 双语入口是否清楚、会不会被看成已有可安装产品：未运行。草案里写了 `Chrome extension planned`，避免把计划中的扩展写成已经可安装。
- 是否需要副标题或另一名称：未运行。改名不是本实验的前置条件，本轮也没有决定改名。

直接打开仓库网址，或在仓库内部查找文字，都不能代替这三组入口的搜索。

## 未检查

- GitHub REST 搜索：未运行。
- 读取 `GET /repos/victorzhong0110/gold-miner`：未运行。
- GitHub 网页搜索（登录与未登录、地区）：未检查。
- 普通搜索引擎：未检查。不假设仓库已被收录。
- 应用简介、topics、许可证：未做。权限未在本轮核验。
- Chrome 商店：不适用。没有可安装扩展。

## 复现

只打印计划，不访问网络：

```bash
python3 experiments/E8-discoverability/scripts/e8_materials.py
python3 experiments/E8-discoverability/scripts/test_w7_materials.py
```

计划里的 URL 是以后可以手工或另开批次执行的请求式样。本脚本拒绝 `--live`，不会读取 `GITHUB_TOKEN`，也不会发出 HTTP 请求。

以后若另开日期文件做真实复测：先确认有权应用元数据再改仓库设置；搜索遇限流即停止；接口错误单独记录，不能写成零结果；新结果不要覆盖本文件和 9 月 17 日基线。
