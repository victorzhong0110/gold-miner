# PR1 review fixes — brief note (2026-09-17)

对应分支 `opencode/gui-w1-w8`。本文件为审查意见落地简记，证据以代码/测试/结构化产物为准，不替代运行证据。

## 落点

- `experiments/E1-cross-language-search/scripts/e1_minimal_runner.py`：两阶段合并，先跑完 ALL budgeted variants（respect cancel）收集 `per_query_records`，再合并/去重/排序/截断至 `MERGED_TOP_N`；不再因单查询填满而提前 break 外层循环。
- 来源保留：`per_query_records` 保留每命中 variant/query/rank/page；`merged_candidates` 去重但保留全部 `sources:[{variant_query,api_query,variant_lang,rank,page},…]`，非仅首见。
- 计数：`attempted_requests / successful_requests / failed_requests / cancelled_variants`；失败计入成本，成功数不等于成本；`actual_requests` 保留为 `successful_requests` 别名兼容。
- `schemas/candidates.schema.json`：`arm` 允许 M 并保留 A/B/C/D，`sources` 已文档化，`additionalProperties:false` 保持。
- `schemas/judgments.schema.json`：按 `judgment-guide.md L19` 增加必填 `worth_following` 与 `reason`，`additionalProperties:false` 保持；新增 `scripts/test_schemas.py`（jsonschema 优先否则轻量 required 检查）。
- W2：新建新鲜结构化产物 `experiments/E1-cross-language-search/w2-probe-2026-09-17.json`（2026-09-17T20:19:11Z–20:19:32Z，无凭据，4 探测，含 timestamps/query/HTTP status/rate-limit headers/incomplete_results/top-3/matched-field 汇总；失败则 `blocked:true`，本批全部 200）；`w2-source-check-2026-09-17.md` 已指向该 JSON 并声明散文不是替代品。

## 验证

- `python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"` → 100 tests OK，无网络、无密钥。
- E1/E2 首轮仍记“未运行”；未编造 GitHub 结果、指标、额度。
