---
name: can-debug
description: '分析 CAN 或 CAN FD 抓包，按确认的适配器和监听模式采集帧或按明确授权发送。'
---

# CAN / CAN FD 诊断

已保存捕获按测试计划提取单值后可接 [台架核验](../hardware-design-review/references/bench-results.md)。保留原始日志及采集身份。

1. 对日志记录实际总线、通道、时间基准与记录模式，核对波特率和 CAN FD 数据速率。按标准 / 扩展帧 ID、DLC、有效负载、周期和错误帧整理证据。
2. 需现场时验证适配器及驱动是否在 listen-only 模式、是否会 ACK、终端电阻和隔离是否符合测试条件。Windows 厂商 API 和 Linux SocketCAN 按实际环境选择。
3. 发送、主动扫描、总线管理、可能影响总线的模式变更按[硬件操作权限](../hardware/references/permission-gates.md)核对许可、ID、帧内容、发送周期、次数和截止。先保存只读证据，获准后对本次范围做最小试验。
4. 报告观测窗口和过滤器。对照 DBC 或项目文档解释 payload，保留未证实的物理量和位域。

[Linux SocketCAN 文档](https://docs.kernel.org/networking/can.html)
