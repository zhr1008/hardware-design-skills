---
name: flash-jlink
description: '用 SEGGER J-Link 指定探针、芯片、接口和镜像，核对写入及验证。'
---

# J-Link 烧录

先确认探针序列号、厂商支持的精确 Device 字符串、SWD/JTAG、目标电压、速度、镜像与基地址。按主机安装名称选 J-Link Commander。

在烧录或可能重置设备前按[硬件操作权限](../hardware/references/permission-gates.md)确认目标、镜像摘要、地址和预期副作用。

核对指定 Commander 脚本的连接、`LoadFile` 参数和错误退出条件。HEX/ELF 依文件地址；BIN 的加载地址由目标布局证据提供。保护区、解锁、擦除和复位分别列明。

[官方工具文档](https://kb.segger.com/J-Link_Commander)
