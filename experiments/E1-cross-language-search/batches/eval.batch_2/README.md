# E1 第二批：提示词一致性修正复测材料

状态：**已准备，未冻结，未运行**。基线 main `168c4efbc73f0ae2a9413298d97ad568022ca8b3`。第一批材料、结果、失败和判断记录保持原样；历史矛盾仍由第一批 `materials-status.json` 如实记录。

本批复用第一批的 20 个原始公开任务、需求、ID 和写作日期，隔离在独立题集、提示词、设置和未来运行目录中。它检验修正提示词后的同题表现，不能当作未见新题、独立确认或严格盲判。第一批的人工相关性判断仍可独立进行；候选数量不代表用途适合度。

修正内容：B/C/M 都禁止 `in:readme`、`in:name`、`in:description`、`language:`、`stars:`、`repo:`、`user:`、`org:` 和仓库名。C 删除了字段/热度许可，明确运行脚本要求两条不同目标语言查询；不足时记 blocked，不补编无关查询。主比较沿用默认字段、原查询和 1/2/4/4 请求上限，README 扩展仅属另行登记的 C/M 配对诊断。本入口不自动运行 D。

## 离线检查

在仓库根目录执行：

```bash
python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p test_e1_batch2.py
python3 experiments/E1-cross-language-search/scripts/query_generation.py \
  --task-id zh2en-dev-01 --arm C --mode fixture \
  --queries experiments/E1-cross-language-search/batches/eval.batch_2/queries.yaml \
  --prompt-profile eval.batch_2
python3 scripts/run_offline_suite.py
```

fixture 输出明确标为 fixture，只有预置生成数据；不会调用模型或 GitHub。回归也以注入 HTTP 响应检查四组执行链，不产生 live 记录。正式评估入口拒绝用 fixture 冒充评估；单条生成入口禁止以本批 profile 绕过冻结执行 live。

## 将来正式执行

1. 材料合并后，按协议在独立、版本化设置文件中填入**已经存在且核对过**的题集、提示词、种子、设置提交 SHA。草案四个冻结指针均为 null，不等于冻结。保留当前题集/提示词 SHA-256，固定模型、2048 输出 token、300 秒超时、零自动重试和串行 GitHub 间隔。
2. 为每次运行选择新的 run-id 与输出目录，核对环境配置与设置一致。密钥仅取自环境，不能写入设置或记录。实际运行、配额等待和费用按真实响应记录，本交付没有发送请求。
3. 使用 `e1_pipeline.py --live --batch eval.batch_2 --queries <本目录 queries.yaml> --settings <独立冻结设置> --run-id <新 ID> --out <新目录>`。运行前核对题集及全部提示词指纹；每次模型请求前再次校验当前提示词，记录实际发送内容的哈希。变更材料必须新批次/设置，不修改既有运行。
4. 失败照实保留，不自动重发；旧批与复测结果分开报告，来源遮蔽不等于严格盲判，真实判断和效果结论待人工证据。

`run-settings.draft.json` 的 MiniMax-M3 参数来自已决定的第一批设置，不代表本批已发生费用，也不把未知成本填零。离线通过与浏览器 fixture 通过都不能替代真人使用验收。
