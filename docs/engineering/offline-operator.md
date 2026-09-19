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

D 组只产生 stub：`blocked` / `未运行`。

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
