# E3 观察记录（2026-09-22）

6 条公开片段在冻结后，用 Google Translate 的 `client=gtx` 接口各译一次。沉浸式翻译未运行。Chrome 内置翻译界面未运行。个人模型未调用。自建翻译比较未运行。判定人是 `w6-technical-check`，只做技术核对。

这 6 条里的计数只描述这 6 条和这个工具，不是准确率，也不决定搜索、推荐或要不要自建翻译。

## 改变了理解的条目

- P-01（Umi-OCR README 第 171 行，zh→en）：反引号里的选项名被译成英文，“自然段”写成 segment。“不区分多栏布局”的否定还在。
- P-04（Express Readme.md 第 125–127 行，en→zh）：“does not force”仍是“不会强迫”。原文在 `over` 与 `14` 之间换行，译文把“支持超过”拆开，14 前面的“超过”没有了。链接还在。
- P-05（requests README 第 12–13 行，en→zh）：`import requests` 被写成“导入请求”。下一行的 `requests.get` 和 URL 还在。

## 这批没有记成严重误译的条目

- P-02：忽略范围“整个文本块而不是单个字符”还在，`key_mouse`、`pubsub_connector.py`、`pubsub_service.py` 原样保留。
- P-03：issue 评论里“看了源码，所以 Mac 没法用”还在。
- P-06：让步和 `but` 之后的“不修”还在。`more trouble than not` 收成了“会造成更多麻烦”。`git fsck` 文本还在，反引号变成中文引号。

等待见 `translations.jsonl` 的 `elapsed_ms`：1146、653、908、532、686、288。单位是毫秒，只属于这次请求。工具版本未知。
