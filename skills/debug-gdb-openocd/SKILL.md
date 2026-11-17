---
name: debug-gdb-openocd
description: '用 GDB 与 OpenOCD 诊断嵌入式目标，结合匹配 ELF、寄存器、回溯和故障状态定位。'
---

# GDB 与 OpenOCD 调试

1. 从已有日志、转储与匹配 ELF 还原符号地址和回溯。记录构建版、符号与当前板是否一致。
2. 确需现场时，核对探针身份、目标配置、现有服务器及连接地址。阅读 OpenOCD 配置初始化、`reset`、`halt`、`examine` 和事件钩子。按[硬件操作权限](../hardware/references/permission-gates.md)取得可能暂停、复位或写入的操作许可。
3. 使用匹配的 GDB 连接已核实的本地远端。先读取任务需要的栈、寄存器和故障状态。关注地址范围、读取副作用及外设寄存器的读清除语义。
4. `load`、写寄存器、断点、继续或复位分别核对作用。结束时按授权保留或恢复目标状态。

[OpenOCD 指令文档](https://openocd.org/doc-release/html/General-Commands.html)
