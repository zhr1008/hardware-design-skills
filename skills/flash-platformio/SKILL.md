---
name: flash-platformio
description: '按指定 PlatformIO 环境和探针/串口上传固件并核查复核结果。'
---

# PlatformIO 烧录

核对 `platformio.ini` 的 environment、`upload_protocol`、端口与实际目标芯片。使用指定的构建工件；对照项目 uploader 是否会自动编译、改熔丝或复位。

在烧录或可能重置设备前按[硬件操作权限](../hardware/references/permission-gates.md)确认目标、镜像摘要、地址和预期副作用。

在确认范围后选择 `pio run -d PROJECT -e ENV -t upload --upload-port PORT` 或该上传器的明确调用。分别报告构建、上传校验、复位和启动证据。

[官方工具文档](https://docs.platformio.org/en/stable/core/userguide/cmd_run.html)
