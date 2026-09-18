# W7 项目发布元数据与 E8 复测准备（2026-09-17，部分运行）

对应：`docs/backlog.md` W7、`docs/plan/v0.4.md` W7、`docs/decisions/0001-project-name.md`、`docs/decisions/0003-license.md`、`experiments/E8-discoverability/template.md`。
约束：不改仓库名（AGENTS.md 第 8 条）、不添加 LICENSE（第 9 条）、名称/许可“建议”不写成已决定（第 10 条）、H1 未验证前不写扩展（第 2–4 条）。

## 1 做了什么

- 元数据文案：复用 0001 已有草案，不新编、不应用到仓库设置：
  - 简介草案：`黄金矿工 Gold Miner：用自己的语言发现、阅读和探索 GitHub 项目。Cross-language GitHub project discovery and exploration; Chrome extension planned, Chinese/English first, bring your own API.`
  - topics 草案：`chrome-extension, browser-extension, github, cross-language, cross-lingual-search, project-discovery, readme-translation, chinese, english, bring-your-own-key`（实际格式与数量在应用时核对）。
- 许可证：复用 0003 备选（代码 MIT 建议 / Apache-2.0；文档 CC BY 4.0 建议；译文包原则），本次未决策、未添加 LICENSE，试用交付前明确。
- E8 复测：按模板准备查询组（站内去掉 `GitHub` 一词），尝试无凭据 API 复测；因配额耗尽两次 403，未取得新结果（见第 3 节）。网页端与普通搜索引擎未检查。

## 2 证据在哪里

- 文案证据：`docs/decisions/0001-project-name.md` 第 3 节（本次只整理文案，没有修改仓库设置）；许可证据：`docs/decisions/0003-license.md`（状态待决策）。
- 复测尝试（实际运行，均失败，未伪造结果）：
  - `2026-09-17T19:40:42Z`：`GET /repos/victorzhong0110/gold-miner` → `HTTPError 403 rate limit exceeded`（AUTH unauthenticated）。
  - `2026-09-17T19:42:06Z`（75 秒后重试 1 次）：同端点 → 同样 `403 rate limit exceeded`。
  - 按工程检查第 1 节，遇限流即停止，未继续追加搜索查询。
- 基线保留：首次探测 `experiments/E8-discoverability/2026-09-17-probe.md`（简介空、topics 空、无许可证条件下的 9 查询记录）仍为当前唯一 E8 基线，本轮未覆盖它。

## 3 失败或未知是什么

- 失败：E8 API 复测 2 次均因无凭据配额耗尽失败（W2 观测核心 `remaining 4`，搜索 `remaining 7`；后续窗口未恢复）。失败已记录为配额边界，不是零结果。
- 未知：
  - 本仓库当前简介/topics/许可证状态：未知（本次未能成功读取；不得沿用 9-17 基线当作当前状态）。
  - 站内名称加用途、纯用途查询的当前位置：未知（未取得）。
  - GitHub 网页搜索（登录/未登录、地区）、普通搜索引擎收录：未检查。
  - 应用元数据所需权限：未验证（有权限再应用并复测，见 v0.4 W7）。

## 4 下一工作包是否具备输入

- W8 具备输入：元数据草案可用、许可仍待决策、E8 基线保留但复测未完成——可发现性结论只能引用 9-17 基线并注明条件已可能变化。
- W14（开源试用与 E8 完整检查）：不具备，需许可明确加元数据应用后的三入口（API/网页/外部搜索）复测。
- 下一步最小动作：待配额恢复后，用模板新日期文件重跑全部查询并互链 0001；应用简介/topics 前确认账号权限。
