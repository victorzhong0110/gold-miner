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

这条 fixture 命令里的 D 组仍然只产生 stub：`blocked` / `未运行`。不能把 fixture 抄进 `runs/` 当成强对照。

正式 D 组是另一条命令（2026-10-04 决定见 `docs/decisions/0004-minimax-d-group.md`）。它调用 MiniMax-M3 的 Responses API 服务端 `web_search`，再核对仓库是否存在。没有密钥时退出码非 0，不创建运行目录。

```bash
export OPENAI_API_KEY="$MINIMAX_API_KEY"
export OPENAI_BASE_URL=https://api.minimax.cn/v1
export OPENAI_MODEL=MiniMax-M3
python3 experiments/E1-cross-language-search/scripts/e1_d_assistant.py \
  --live --wait-for-quota \
  --run-id 2026-10-04-d-minimax \
  --out experiments/E1-cross-language-search/runs/2026-10-04-d-minimax
```

配额或 GitHub 限流停在未完成任务上。同一 `--out` 再执行一次即从该任务继续。只有「模型返回可解析名单且核对跑完」的题算完成；超时、HTTP 错误、没有名单的题续跑时重新请求模型（每次调用每题最多 `--model-attempts` 次，默认 3；单次超时 `--model-timeout`，默认 300 秒）。GitHub 对改名/转移仓库返回的 301 会被跟随，按新名记为存在；跟不到的核对续跑时重核，不再请求模型（`--reverify-only` 只做这一步）。人工用途判断不在这条命令里。

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

## D组结果之后

D组2026-10-04已完成20题，记录见runs/2026-10-04-d-minimax；用途判断及B/C/M仍未运行。已合入的runner会拒绝续跑时换run_id、模型、端点、prompt或题集，截断回答不能算完成，接口拒绝8192上限不会取消上限重发。

B/C/M查询生成器已统一2048输出token（含推理），默认60秒超时；设置BYOK_TIMEOUT_SECONDS会覆盖默认值。一次请求、不自动重试；think不当成最终JSON，length保留失败。比历史256token设置可能多用token/等待时间，实际费用未知。正式新批次须冻结具体参数及已有代码SHA；不要续写到D的目录。当前环境缺模型密钥，未调用付费接口。

真实A/B/C/M入口必须显式提供新--run-id，输出目录已含pipeline.json时拒绝覆盖；任何请求前检查模型配置，结果包含source_sha、settings_sha256和batch（参数快照在generation_records，不复制可能含私密值的配置文件）。正式eval仍须冻结。已存在的D目录不得用于此命令。

```sh
python3 experiments/E1-cross-language-search/scripts/e1_pipeline.py \
  --live --batch eval.batch_1 --run-id YOUR_NEW_BCM_RUN_ID \
  --settings /path/to/frozen-settings.json --out /path/to/new-bcm-run
```
