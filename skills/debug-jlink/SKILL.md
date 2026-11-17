---
name: debug-jlink
description: '使用 SEGGER J-Link GDB Server 调试已确认的硬件目标和匹配符号。'
---

# J-Link 调试

先核对目标板、芯片、探针序列号、接口、电压和速度。保存当前 ELF 或符号文件的摘要。检查本机服务器的绑定地址和目标身份。命令行版本和图形版通过实际可执行文件区分。

按[硬件操作权限](../hardware/references/permission-gates.md)核对连接时的暂停行为、初始化、窗口和允许的退出状态。只依据本次目的使用栈、寄存器或指定内存范围。目标寄存器可能读清除。将已授权的断点、下载、复位和恢复运行逐项记录。用户需要只读诊断时优先分析已有符号和日志。

[SEGGER J-Link GDB Server](https://kb.segger.com/J-Link_GDB_Server)
