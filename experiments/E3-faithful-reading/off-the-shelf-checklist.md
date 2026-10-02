# E3 现成翻译检查清单 + 错误分类

对照协议仍见 `translation-contrast-2026-09-18.md`。本清单用于真实片段集 `fragments-real-2026-09-19.md`。
**对照输出未运行。**

## 每次运行必填

- 工具名 / 版本 / 浏览器版本（未知就写未知）
- 语言对、原文是否可见
- 片段 id、译文、回查原文位置

## 错误分类（机器可读）

| code | 含义 |
|---|---|
| `term_drift` | 术语变成另一概念 |
| `negation_flip` | 否定/「请勿」极性丢失或反转 |
| `constraint_softened` | 限制被说成建议 |
| `code_broken` | 标识符/命令/UTI 被翻译坏 |
| `relation_lost` | issue 问答指代错乱 |
| `format_broken` | 列表/链接/代码块损坏 |
| `tool_failed` | 工具失效/超时 |
| `unrun` | 未运行 |

流畅度加分不得抵消上述错误。无缺口不得启动自建翻译比较。
