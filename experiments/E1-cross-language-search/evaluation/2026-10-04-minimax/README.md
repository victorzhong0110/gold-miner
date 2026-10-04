# 2026-10-04 MiniMax-M3 判定材料

先看 [blind-sheet.md](blind-sheet.md) 或 [blind-candidates.jsonl](blind-candidates.jsonl)，对照 [判定口径](../../judgment-guide.md)。233 个题目/仓库组合，覆盖 311 个组内检查位置（A30/B64/C73/M46/D98）。不足 5 个的组保留实际数量，阻断不补候选。

这是已准备的材料，不是判定结果。来源为同日 A/B/C/M 和 D 的原始记录；两个运行时间及请求预算不同。独立仓库数、任务内适合度与个人新发现必须分别报告。不要用结果数量判断好坏。

来源映射在 blind-key.json，仅供分析者回填；判定前不要查看。原运行 judgments.jsonl 仍为空。

## ⚠ 这批材料不是盲判，是来源遮蔽，且遮蔽可被机械还原

`blind_eval.py:40` 用 `blind_id = sha256(run_id + ':' + task_id + ':' + repo)[:16]`，
**arm 不在哈希输入里**（blind_id 同时充当去重键，所以同一仓库跨组出现时只判一次）。
因此任何拿到公开运行记录的人都能重算分组，**不需要打开 blind-key.json**。

对本文这批材料实测（`--audit-masking`）：

| 指标 | 数值 |
|---|---|
| blind_id 总数 | 233 |
| 组别可完整还原 | 233 / 233 |
| **可确定归属单一组** | **196 / 233（84%）** |
| A / B / C / D / M 单组可确定 | 4 / 32 / 43 / 95 / 22 |

即 **A 组基线 4/4 全部暴露，D 组 95 条可确定**。剩余 37 条之所以不明确，
只是因为同一仓库跨多个组出现、组别是集合而非单值——那是去重的副作用，不是遮蔽。

自查（不需要 key，不写判定材料）：

```sh
python3 experiments/E1-cross-language-search/scripts/blind_eval.py \
  --pipeline experiments/E1-cross-language-search/runs/2026-10-04-bcm-minimax/pipeline.json \
  --d-run experiments/E1-cross-language-search/runs/2026-10-04-d-minimax \
  --out /tmp/masking-audit --audit-masking
```

**要真正遮蔽需要一处不存放在本仓库的私密 salt。** 那是判定人（发起人）持有的东西，
仓库里不能生成、也不该生成假 salt 来充数。因此本轮只做两件事：把可还原程度测出来，
并把上面的披露从「映射在同一仓库」改成实际强度。

**判定前请披露已见信息。** 若按现状判定，结论必须写成「带已知可还原分组属性的来源遮蔽判定」，
不能写成盲判；本记录不替判定结果背书。

重建候选与映射（无网络、无模型请求）：

```sh
python3 experiments/E1-cross-language-search/scripts/blind_eval.py \
  --pipeline experiments/E1-cross-language-search/runs/2026-10-04-bcm-minimax/pipeline.json \
  --d-run experiments/E1-cross-language-search/runs/2026-10-04-d-minimax \
  --out experiments/E1-cross-language-search/evaluation/2026-10-04-minimax
```

真人完成后，用既有 blind_eval.py 的 --key、--judgments、--judge-kind human 做结构校验和分析。生成脚本不替人填写判断；分析结果仍需按协议复核，特别是缺失、零候选和部分失败组，不能直接把脚本集合差当成 H1 结论。
