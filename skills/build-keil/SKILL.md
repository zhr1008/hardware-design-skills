---
name: build-keil
description: '用 µVision 构建指定 Keil 工程目标并验证日志和实际镜像。'
---

# Keil / µVision 构建

确定 `.uvprojx` 文件、真实 target、编译器和 Pack/设备定义版本。确定 UV4 可执行文件及是否带来窗口；无法排除时按前台权限处理。

经过项目授权后调用 `UV4 -b PROJECT -t"TARGET" -o"LOG"`。等待日志落盘，检查编译器错误和警告，确认该 target 输出 AXF/HEX 以及生成时间。首次安装、调试和烧录另作独立操作。

交付工具/配置、执行状态、日志定位与已验证的工件路径。已有项目钩子可能写文件或访问网络。按[硬件操作权限](../hardware/references/permission-gates.md)检查任务内允许的目录、启动影响及外发范围。

[官方命令文档](https://www.keil.com/support/man/docs/uv4cl/uv4cl_commandline.htm)
