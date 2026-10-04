# 0.1.4 真机问题修复

反馈来源：docs/session-issues-2026-10-04 分支，提交1b5eb97b61d9ad79fe90ca8c6853473c32b5c5c8。原始记录保留在docs/session-issues.md，没有重新请求发起人转述。

修复S1/S3/S5/S6，补S2来源和区域说明。S2原描述与最新官方文档不符：2026-10-04大陆官方页明确列api.minimax.cn，国际列api.minimax.io，未更改用户已保存的端点。401/1004不自动判断区域错误。

探测读取当前输入且不保存密钥；输入变化中止旧请求并阻止迟到绿灯。实际工作请求和两处探测2048token，不重试；think内容不充当最终答案，length拒绝为截断输出；探测要求pong。面板固定视口右侧，宽高受限、内部可滚动，关闭/取消保留。增大预算可能增加实际费用/等待，上限不是实际用量。

离线268项Python与58项Node通过。新增浏览器fixture检查当前输入/空输出/迟到响应和无main的6000px页面可见性，[CI37194278583](https://github.com/victorzhong0110/gold-miner/actions/runs/37194278583)的11项fixture验收全部通过。无真实模型调用或密钥读取；用户原始单次观察没有被升级为产品效果。

S4依然owner-blocked：D是独立联网助手强对照，不是把同一套B/C/M改名。工具、模型和预算未冻结；本轮不替发起人作该决定。

[PR14](https://github.com/victorzhong0110/gold-miner/pull/14)为本次交付，合并状态以GitHub为准；源码3c186e0135a13329645ee9afadc57e2056e7ec3c，浏览器生产脚本哈希与0.1.4包一致。
