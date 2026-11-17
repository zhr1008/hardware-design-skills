---
name: debug-platformio
description: '核对 PlatformIO 调试环境和配置，按授权连接目标、调试并保存证据。'
---

# PlatformIO 调试

1. 确定 `platformio.ini` 的环境、板、调试适配器、符号文件和 `debug_*` 配置。核对 `debug_load_mode`、初始化命令、服务端和调试构建差异。
2. 先用保存的日志与 ELF 分析。现场启动 `pio debug -d PROJECT -e ENV` 前明确可能编译、下载、暂停、复位或占用端口。
3. 按[硬件操作权限](../hardware/references/permission-gates.md)取得本次动作许可。检查实际目标、当前断点和连接状态。以故障寄存器、回溯和源代码位置交付证据，并按约定结束目标会话。

[PlatformIO 调试命令](https://docs.platformio.org/en/stable/core/userguide/cmd_debug.html)
