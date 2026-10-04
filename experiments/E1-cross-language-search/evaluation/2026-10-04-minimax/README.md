# 2026-10-04 MiniMax-M3 判定材料

先看 [blind-sheet.md](blind-sheet.md) 或 [blind-candidates.jsonl](blind-candidates.jsonl)，对照 [判定口径](../../judgment-guide.md)。233 个题目/仓库组合，覆盖 311 个组内检查位置（A30/B64/C73/M46/D98）。不足 5 个的组保留实际数量，阻断不补候选。

这是已准备的材料，不是判定结果。来源为同日 A/B/C/M 和 D 的原始记录；两个运行时间及请求预算不同。独立仓库数、任务内适合度与个人新发现必须分别报告。不要用结果数量判断好坏。

来源映射在 blind-key.json，仅供分析者回填；判定前不要查看。映射公开保存在同一仓库，因此只是来源遮蔽材料，不能保证判定人未见组别。请披露已见信息。原运行 judgments.jsonl 仍为空。

重建候选与映射（无网络、无模型请求）：

```sh
python3 experiments/E1-cross-language-search/scripts/blind_eval.py \
  --pipeline experiments/E1-cross-language-search/runs/2026-10-04-bcm-minimax/pipeline.json \
  --d-run experiments/E1-cross-language-search/runs/2026-10-04-d-minimax \
  --out experiments/E1-cross-language-search/evaluation/2026-10-04-minimax
```

真人完成后，用既有 blind_eval.py 的 --key、--judgments、--judge-kind human 做结构校验和分析。生成脚本不替人填写判断；分析结果仍需按协议复核，特别是缺失、零候选和部分失败组，不能直接把脚本集合差当成 H1 结论。
