---
name: flash-keil
description: '按明确的 Keil 目标和器件 Flash 算法下载固件，检查原生日志与校验。'
---

# Keil / µVision 烧录

核对项目 target、实际输出、已选调试器、Flash algorithm、地址范围和复位选项。用户审批覆盖具体物理写入与可能的应用窗口。

在烧录或可能重置设备前按[硬件操作权限](../hardware/references/permission-gates.md)确认目标、镜像摘要、地址和预期副作用。

用当前 µVision 文档给出的下载入口，如 `UV4 -f PROJECT -t"TARGET" -o"LOG"`。对照日志中的探针与擦写/校验范围核实结果。

[官方工具文档](https://www.keil.com/support/man/docs/uv4cl/uv4cl_commandline.htm)
