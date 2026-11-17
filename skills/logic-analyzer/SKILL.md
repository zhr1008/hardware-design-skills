---
name: logic-analyzer
description: '读取逻辑分析仪已保存的数字采样，或按确认条件用 Saleae Logic2 等工具采集和解码。'
---

# 数字逻辑分析

先读已有捕获和通道表。确认通道对应的电平、采样率、触发、边沿极性、解码参数、时间基准与持续时间。保留原始捕获与转换后数据，报出实际解码覆盖和错误。

使用 Saleae Logic2 时按当前 Automation API 核对服务、设备、采样率与协议分析器。需要启动应用、改变前台、现场连接或采集时首先按[硬件操作权限](../hardware/references/permission-gates.md)落实本次动作。诊断结论注明真实采样范围，电气幅度、过冲及模拟边沿另由适用仪器取得。

[Saleae Logic 2 Automation 文档](https://saleae.github.io/logic2-automation/)
