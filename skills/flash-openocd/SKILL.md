---
name: flash-openocd
description: '按确认的探针及目标配置用 OpenOCD 写入并校验指定镜像。'
---

# OpenOCD 烧录

读取项目使用的 adapter、board/target 配置及 reset 行为，确认具体硬件、速度和 Flash 布局。审查配置与附带脚本。

在烧录或可能重置设备前按[硬件操作权限](../hardware/references/permission-gates.md)确认目标、镜像摘要、地址和预期副作用。

按官方 Flash Programming 契约选择写入、`verify` 与退出方式。`program` 默认先执行 `reset init`，使目标复位并暂停。附加的 `reset` 参数会在校验后请求 `reset run`。这些动作均须落在获准范围内。核对地址、日志和校验范围。

[官方工具文档](https://openocd.org/doc-release/html/Flash-Programming.html)
