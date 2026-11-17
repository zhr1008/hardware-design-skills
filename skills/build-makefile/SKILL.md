---
name: build-makefile
description: '按项目 Makefile 规则构建指定目标，保留环境、日志及产物证据。'
---

# Makefile 构建

确定项目工作目录、指定 Makefile、编译器环境、预期目标和递归 make 行为。阅读目标下具体命令与依赖。

按工程约定调用 `make -C PROJECT TARGET`，显式给出需要的变量。GNU make 的 `--just-print` 与含 `$(MAKE)`、`${MAKE}` 或 `+` 的递归命令有特殊行为，安全预览先读规则。检查实际退出状态和工件。

交付工具/配置、执行状态、日志定位与已验证的工件路径。已有项目钩子可能写文件或访问网络。按[硬件操作权限](../hardware/references/permission-gates.md)检查任务内允许的目录、启动影响及外发范围。

[官方命令文档](https://www.gnu.org/software/make/manual/html_node/Instead-of-Execution.html)
