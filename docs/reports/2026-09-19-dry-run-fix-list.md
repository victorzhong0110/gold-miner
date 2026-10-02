# 干跑安装问题清单

环境：Cloud Agent Linux，无图形 Chrome。**真机加载未运行。**

静态干跑（本分支已做）：

- `manifest.json` 可解析为 MV3。
- `node --test extension/tests/test_shared.mjs` 覆盖排序/去重/导出清洗。
- `node --test extension/tests/test_background.mjs` 覆盖 service worker 消息流（隔离、模型注入、失败不缓存、反馈重排、explore、导入复用）。
- `python3 scripts/test_extension_package.py` 扫扩展树密钥模式。
- `bash extension/scripts/build.sh` 生成 unpacked + zip。

未跑因此可能存在的问题（待 Victor 真机）：

1. GitHub 新版 DOM 导致面板位置难看或重复 —— 需看 sticky 面板是否挡搜索框。
2. 真机再确认 `chrome.storage.local.setAccessLevel`；离线已 fail-closed，但 Chrome 版本差异 **未运行**。
3. turbo 导航漏钩 —— 前进后退后是否双注入。
4. 无 token 时 Search API 403/限流文案是否可读。
5. 选项页探测连接的 CORS / host 权限（optional_host_permissions 可能要用户允许）。

复测记录见 [2026-09-19-retest-notes.md](2026-09-19-retest-notes.md)。
