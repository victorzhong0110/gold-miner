# W2 候选来源与配额检查（2026-09-17，实际运行）

对应：`docs/backlog.md` W2、`docs/plan/v0.4.md` W2、`docs/engineering/prerequisites.md` 第 1 节、E1 协议第 1 节。
状态：小规模诊断已运行；E1 评估运行未开始。

## 1 做了什么

- 无凭据路径（未设置 `GITHUB_TOKEN`，`env` 检查为 False）串行探测 GitHub REST：
  - `GET /rate_limit` 1 次（核心配额可见性）。
  - `GET /search/repositories` 3 次，每次 `per_page=5`，间隔 5 秒：
    1. `clipboard history manager`（默认字段，英文短词诊断）。
    2. `clipboard history manager in:readme`（同需求显式 README 字段对照）。
    3. `局域网文件互传`（中文短语默认字段诊断）。
- 请求头含 `Accept: application/vnd.github.text-match+json`、`User-Agent: E1-w2-check/1a`。
- 未使用任何凭据，未调用模型，未做人工判定，未启动 E1 A/B/C/M/D 比较。

## 2 证据在哪里

- 本文件即 W2 报告；原始命令见第 4 节复现块。
- 实际运行时间：`2026-09-17T19:39:10Z` 起，Python `urllib` 同步串行。
- 本地可运行检查：`python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"`（70 tests OK，见 W1；W2 未新增断言型测试， live 探测不可重复断言为通过）。
- 实际返回（原样摘要，未编造）：
  - `rate_limit`：`status 200`，`x-ratelimit-limit 60`，`remaining 4`。
  - 默认英文短词：`status 200`，`total_count 878`，`incomplete_results false`；前 3 为 `SUPERCILEX/gnome-clipboard-history (625, props description+name)`、`SUPERCILEX/clipboard-history (487, description+name)`、`gustavosett/Windows-11-Clipboard-History-For-Linux (977, description+name)`；搜索配额 `limit 10, remaining 9`。
  - README 显式字段：`status 200`，`total_count 33068`，`incomplete_results false`；前 3 为 `p0deje/Maccy (21618, text_matches props [])`、`jaywcjlove/awesome-mac (114024, [])`、`EcoPasteHub/EcoPaste (7417, [])`；`remaining 8`。
  - 中文短语：`status 200`，`total_count 153`，`incomplete_results false`；前 3 为 `zhoubowen-sky/LingDong (961, description)`、`zhoubowen-sky/LingDongWeb (29, description)`、`zhoubowen-sky/File-Transmit-pc (30, description)`；`remaining 7`。

## 3 失败或未知是什么

- 失败：无。本轮 4 次请求全部 `200`，无超时、无限流、无 `retry-after`。
- 未知/边界：
  - 无凭据搜索配额为每分钟 10 次（本轮观测 `limit 10`），核心 `rate_limit remaining 4` 说明共享出口配额紧张；E1 全量（20 任务 × 多组 × 多查询）不可在无凭据下一次跑完，必须分批、串行、按 `remaining/reset` 退避，必要时再引入用户最小权限凭据（本次未引入）。
  - README 组前 3 的 `text_matches` 为空数组，`matched_fields` 按协议只能记 `unknown`，不能按标题相似度补造。本次未解析完整 `text_matches` fragment，仅记录 `property` 集合；正式 E1 须按 `scripts/github_search.py:extract_matched_fields` 逐条记录。
  - 中文短语有结果（153）不等于中文项目空间可检索；可能是分词、索引、查询表达或窗口截断的任一作用。英文 README 数量差异（878 vs 33068）主要是字段放宽，不是跨语言增益证据。
  - 方法偏差披露：诊断 3 用 `局域网文件互传`，与 `queries.yaml` eval `zh2en-eval-01`（`局域网文件互传 工具`）仅相近而不完全相同（后者多 `工具` 二字）。这是 W2 接口诊断，不是 E1 运行：未做任何方法组比较、未做判定、未计入任何指标。E1 评估仍为未运行，正式运行前须冻结并另开批次；本条重合已在此披露，后续不得将本轮 `total_count`/前 3 当作 E1 证据引用。

## 4 复现（未写入任何密钥）

```bash
python3 - <<'PY'
import urllib.request, urllib.parse, json, time, datetime
def call(path, params):
    url = f"https://api.github.com{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent":"E1-w2-check/1a","Accept":"application/vnd.github.text-match+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
        hdrs = {k.lower(): v for k,v in r.headers.items()}
        return {"status": r.status, "limit": hdrs.get("x-ratelimit-limit"), "remaining": hdrs.get("x-ratelimit-remaining"), "total": data.get("total_count")}
print(call("/rate_limit", {})); time.sleep(5)
print(call("/search/repositories", {"q": "clipboard history manager", "per_page": 5})); time.sleep(5)
print(call("/search/repositories", {"q": "clipboard history manager in:readme", "per_page": 5})); time.sleep(5)
print(call("/search/repositories", {"q": "局域网文件互传", "per_page": 5}))
PY
python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"
```

## 5 下一工作包是否具备输入

- W3 具备输入：无凭据路径可用但配额緊；`scripts/github_search.py` 的串行 2 秒、去重、`matched_fields unknown` 规则已验证可用。W3 Runner 必须实现预算计数、来源保存、取消与错误记录，且默认串行、按限流退避。
- W4 不具备输入：W3 Runner 与冻结提交尚未完成，模型未配置，种子集仍为草案；E1 首轮继续记“未运行”。

交付四项：见上 1/2/3/5 节。未运行项已标“未运行”，未用计划文档替代证据。
