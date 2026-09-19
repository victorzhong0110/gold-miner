# E1 提示词使用说明

对应协议：`experiments/E1-cross-language-search/protocol.md` 第 3 节（方法组）。预算以 `../run-settings.json` 为准：A 最多 1 次 GitHub 请求（0 次模型请求）、B 最多 2 次（最多 1 次模型请求）、C/M 各最多 4 次（各最多 1 次模型请求）；D 为联网助手强对照，不计 GitHub 预算。

## 三个文件何时用

- `b-translate.txt`：B 组「简单译词」对照用。同一任务下，对一条用户原话执行一次，得到另一语言的一条查询。两条查询（原文一条＋译文一条）各取前 30，再合并去重。每任务最多 2 次 Search API 调用、最多 1 次模型调用。
- `c-rewrite.txt`：C 组「跨语言扩展」。同一任务下执行一次，得到最多 2 条中文加最多 2 条英文查询。`in:readme` 不在本步写出；README 字段由运行脚本做 C/M 配对诊断，主结果与 README 轮分开报告。每任务最多 4 次 Search API 调用、最多 1 次模型调用。
- `m-rewrite.txt`：M 组「同语言扩展」。同一任务下执行一次，得到最多 3 条**同一语言**查询（加上原查询最多 4 次 GitHub 请求）。禁止输出另一语言。每任务最多 4 次 Search API、最多 1 次模型调用。
- `d-assistant.txt`：D 组「强对照」用。把用户原话粘贴进方括号位置，原样发给一个支持联网的通用 AI 助手。限时 5 分钟。记录它给出的仓库并逐个核实存在，不存在的计为幻觉。

A 组（原生）不用提示词文件，直接用用户原始查询做 GitHub 默认搜索，取前 30。

## 输入输出例子

### B 组（`b-translate.txt`）

输入：

```text
用户原话：我想找一个支持断点续传的命令行下载工具
方向：en
```

输出（只能是这一行 JSON）：

```json
{"other_lang":"en","query":"a command-line download tool with resume support"}
```

### C 组（`c-rewrite.txt`）

输入：

```text
用户原话：我想找一个支持断点续传的命令行下载工具
```

输出（只能是这一行 JSON）：

```json
{"zh":["断点续传 命令行 下载","命令行 下载器 续传"],"en":["cli download resume","command line download manager resume"],"notes":"同义用途词；in:readme 留给脚本在结果不足时追加。"}
```

### D 组（`d-assistant.txt`）

输入（把用户原话粘贴进模板后发出）：

```text
请帮我在 GitHub 上找满足以下需求的仓库。

用户原话：
我想找一个支持断点续传的命令行下载工具

要求：
1. 请在 5 分钟内回答。
2. 只要真实存在的 GitHub 仓库，不准编造不存在的仓库名。
3. 不确定的仓库请先核实，不存在的名字不要输出。
4. 输出格式：owner/repo，每行一个，最多 10 个。
```

输出（示例格式，仓库名仅为占位）：

```text
owner1/repo1
owner2/repo2
```

## 运行中途禁止改提示词

协议第 2 节“冻结方法”规定：运行评估前提交任务、种子、提示词/词表、字段配置、排序、预算、模型标识和运行说明，运行中不改。

因此 `queries.yaml` 的 eval 组一旦提交、运行开始，就不准再改本目录下的任何提示词。如需调整，只能开新一轮运行并如实记录，不得覆盖本轮结果。
