# 2026-10-05：盲判材料的遮蔽强度实测

对 `experiments/E1-cross-language-search/evaluation/2026-10-04-minimax/`
这批待判定材料做了一次遮蔽强度审计。结论：**它不是盲判，是来源遮蔽，
而且遮蔽可以被一段脚本机械还原。** 判定尚未发生（`judgments.jsonl` 仍为空），
所以这个问题在花钱判定之前发现，成本几乎为零。

## 1. 根因

`scripts/blind_eval.py:40`：

```python
blind_id = hashlib.sha256((pipeline['run_id'] + ':' + identity).encode()).hexdigest()[:16]
# identity = task_id + ':' + repo
```

**arm 不在哈希输入里。** 这本身是设计使然：blind_id 同时当去重键用，
同一仓库若在 A/C/M 多个组出现，只判一次、按组分别计入。

但代价是：给定 `run_id`、`task_id`、`repo` 三个公开值，就能算出 blind_id；
而这三个值在 `blind-candidates.jsonl` 里直接可读，`run_id` 也印在材料 README 上。
于是**不需要打开 `blind-key.json`**，拿公开的 `pipeline.json` 就能重算分组。

## 2. 实测结果

用 `--audit-masking`（不读 key、不写判定材料）：

| 指标 | 数值 |
|---|---|
| blind_id 总数 | 233 |
| 组别可完整还原 | 233 / 233 |
| **可确定归属单一组** | **196 / 233（84%）** |
| A 单组可确定 | 4（**4/4 全部**） |
| B / C / D / M 单组可确定 | 32 / 43 / 95 / 22 |

A 组是首轮决策的基线，**4 条全部可确定归属**；D 组 95 条可确定。
剩下 37 条之所以「不明确」，只是因为同一仓库跨多组出现、得到的是组别集合——
那是去重的副产品，不是遮蔽在起作用。

独立验证：把审计结果与真实 `blind-key.json` 逐条比对，A/B/C/M 部分
135/138 完全一致（余下 3 条来自 D 目录，未参与该次载入）。

材料本身可确定性重建：重新生成 `blind-candidates.jsonl` 与 `blind-key.json`
与仓库内版本**逐字节相同**，所以上述测量针对的就是实际材料，不是重建品。

## 3. 原有披露不足在哪里

材料 README 原来写的是：

> 映射公开保存在同一仓库，因此只是来源遮蔽材料，不能保证判定人未见组别。

这句话方向对，但把问题说轻了。它暗示的风险是「判定人可能好奇去翻 key」，
而实际情况是：**即使判定人从不看 key，跑一条命令就能还原 84% 的分组。**
前者靠自觉，后者是工具属性，性质不同。

判定成本不低（233 个题目/仓库组合，311 个组内检查位置）。让人在不知情的
情况下做完再发现分组可还原，代价比先说清楚大得多。

## 4. 修法与为什么不代做

真正遮蔽需要把 arm 掺进哈希输入，即引入一个**私密 salt**：

```
blind_id = sha256(salt + ':' + run_id + ':' + task_id + ':' + repo)[:16]
```

但 salt **不能存放在本仓库**——否则等于没加。所以本轮**不生成** salt，
也不把任何固定字符串写进代码充数（那是安全剧场：仓库是公开的，写死等于没写）。

**机制已就绪，选择权留给判定人。** `blind_eval.py` 现在支持：

```sh
# 1) 判定人在仓库外生成并保管 salt
umask 077 && head -c 32 /dev/urandom | base64 > ~/.e1-blind-salt

# 2) 先自查遮蔽强度（不读 key、不写判定材料）
export E1_BLIND_SALT="$(cat ~/.e1-blind-salt)"
python3 experiments/E1-cross-language-search/scripts/blind_eval.py \
  --pipeline experiments/E1-cross-language-search/runs/2026-10-04-bcm-minimax/pipeline.json \
  --d-run experiments/E1-cross-language-search/runs/2026-10-04-d-minimax \
  --out /tmp/e1-blind --audit-masking
# -> masking_strength: not-derivable-from-public-records

# 3) 生成材料，并把映射写到仓库之外
python3 experiments/E1-cross-language-search/scripts/blind_eval.py \
  --pipeline experiments/E1-cross-language-search/runs/2026-10-04-bcm-minimax/pipeline.json \
  --d-run experiments/E1-cross-language-search/runs/2026-10-04-d-minimax \
  --out <你本地的材料目录> --key-out ~/.e1-blind-key.json
```

设计要点：

- salt **不走命令行参数**。`ps` 和 shell history 都会记录 argv，
  放进去等于放进日志。只从 `E1_BLIND_SALT` 或 `--salt-file` 读取。
- 空白 salt（空串、纯空格）一律当作「没有 salt」，不静默降级成一个弱 salt。
- `--key-out` 让映射表落在仓库外，公开目录里只留 `blind-candidates.jsonl`。
- **salt 挡不住主动看 key 的人。** 它只保证「仅凭公开数据无法反推」。
  判定前仍须披露已见信息。

实测（用临时 salt 验证机制，未写入仓库）：

| 模式 | `masking_strength` | 仅凭公开数据可确定归属 |
|---|---|---|
| 无 salt | `none-mechanical-reversal-possible` | **196 / 233** |
| 有 salt | `not-derivable-from-public-records` | **0 / 233** |

无 salt 时现有材料仍能**逐字节重建**，所以加 salt 是显式选择而非静默改写既有材料。

在 salt 到位之前，这批材料的结论只能写成
「带已知可还原分组属性的来源遮蔽判定」，不能写成盲判。

本轮实际做的：

1. 新增 `blind_eval.py --audit-masking`，让工具**自己报告**遮蔽强度，
   而不是靠 README 文字描述；它不读 key、不写判定材料
2. `test_blind_eval.py` 新增 5 项测试（10 项，原 5 项），
   把「arm 不在哈希输入」这一根因和 84% 这一量级钉住，
   以后改成加 salt 会是一个显眼的、必须同时更新披露的 diff
3. 修正材料 README 的披露段，写明实际强度并给出自查命令

## 5. 验证

- `python3 scripts/run_offline_suite.py` exit 0：**321 Python + 58 Node**（原 316 + 58）
- 审计命令不产生 `blind-candidates.jsonl` / `blind-key.json`，只写 `masking-audit.json`
- 全程未调用真实模型，付费请求 0

本记录不构成 E1/E2/E3 任何效果证据，也不预判判定结果。
它只说明判定材料的遮蔽强度，并要求在判定前如实披露。
