# 离线操作手册

给没有发起人 API、也不想打 GitHub 付费/限流配额的检查。全部命令在仓库根目录执行。

## 1 一次跑完全部离线套件

```bash
python3 scripts/run_offline_suite.py
```

期望：退出码 0。该脚本只跑本地 unittest 与 Node 扩展单测，不读密钥，不访问网络。

分项：

```bash
python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_*.py"
python3 -m unittest discover -s experiments/E3-faithful-reading -p "test_*.py"
python3 -m unittest discover -s experiments/E2-open-ended-discovery -p "test_*.py"
python3 -m unittest discover -s scripts -p "test_*.py"
python3 -m unittest discover -s experiments/E1-cross-language-search/harness -p "test_*.py"
node --test extension/tests/test_shared.mjs
```

## 2 E1 fixture 价值 harness（无网络）

```bash
python3 experiments/E1-cross-language-search/harness/e1_value_harness.py \
  --batch dev \
  --arms A,B,C,M \
  --mode fixture \
  --out /tmp/e1-fixture-run
```

`--mode live` 需要 `GITHUB_TOKEN`（可选）与（B/C/M）模型环境变量；没有配置时脚本必须拒绝并写 `owner-blocked`，不得编造命中。

D 组是**真人强对照**，工具不执行、只录入与比较。按
`experiments/E1-cross-language-search/prompts/README.md` 逐题发给联网助手并核实每个仓库后，
把结果写成 `prompts/d-control.template.jsonl` 那种 JSONL，再录入：

```bash
python3 experiments/E1-cross-language-search/scripts/e1_d_control.py \
  --input <记录的.jsonl> --run-id <run-id>

# 或并入一次批次运行，--arms 里带 D：
python3 experiments/E1-cross-language-search/harness/e1_value_harness.py \
  --batch dev --arms A,D --out /tmp/e1-fixture-run --d-input <记录的.jsonl>
```

命中、幻觉、未核实三者分开计数；没记录的任务保持 `owner_blocked` / 未运行。
没有记录时 D 仍只产生 `blocked` / `未运行`，不会补出结果。

## 3 BYOK 连接探测

```bash
cp config/byok.example.env /tmp/byok.env
# 编辑 /tmp/byok.env 后：
set -a && . /tmp/byok.env && set +a
python3 scripts/check_byok_connection.py
```

未设置 `OPENAI_API_KEY` 时退出码非 0，分类为 `missing_credentials`，并打印「未运行 / owner-blocked」。密钥不得出现在输出里。

## 4 查询生成（B/C/M）

```bash
python3 experiments/E1-cross-language-search/scripts/query_generation.py \
  --task-id zh2en-dev-01 \
  --arm B \
  --mode fixture \
  --out /tmp/qg
```

`--mode live` 无密钥时 `owner-blocked`。每条生成写 JSONL，含 prompt 版本与输入哈希。

## 5 扩展

见 [docs/guides/getting-started.md](../guides/getting-started.md)。本手册不代替 Chrome 真机加载。真机加载在本环境未运行时，报告必须写「未运行」。

## 6 禁止

- 把 fixture 目录抄进 `experiments/E1-cross-language-search/runs/<日期>-*/` 并当成评估运行。
- 在日志、JSONL、导出包里写密钥。
- 用本手册的绿测试宣称 E1/E2/E3 有效。

## 0.1.1 完整检索与盲判入口

`e1_pipeline.py` 支持注入生成与 HTTP 客户端，正式运行用 `--live`；默认不联网，缺少 HTTP 客户端会记录错误而非伪造命中。fixture 完整路径可在测试中验证。正式 eval 要求冻结设置及与 `OPENAI_MODEL` 一致的具体模型。

```bash
python3 experiments/E1-cross-language-search/scripts/e1_pipeline.py --out /tmp/gold-miner-dev
python3 experiments/E1-cross-language-search/scripts/blind_eval.py --pipeline /tmp/gold-miner-dev/pipeline.json --out /tmp/gold-miner-blind
```

默认开发命令缺少检索客户端时可能返回非零，这是未运行而非成功。真实调用命令加 `--live`，使用已有环境变量。判断者仅查看 `blind-candidates.jsonl`，不查看 `blind-key.json`。填写实际 `purpose_fit`、`hard_conditions`、`novel_to_judge`、`worth_following`、`reason`、`judge` 和 `judged_at` 后，使用 `--key`、`--judgments`、`--judge-kind` 分析。未知硬条件不计合适；技术核对不得声称真人新颖性；缺少判定或失败组不输出增益结论。
