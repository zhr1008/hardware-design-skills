---
name: build-platformio
description: '选择 PlatformIO 项目环境并构建固件，核对平台包版本与预期镜像。'
---

# PlatformIO 构建

从 `platformio.ini` 核对真实环境、board、framework、锁定版本和预/后置脚本。确认默认 `targets` 和依赖解析行为。

调用 `pio run -d PROJECT -e ENV`。在构建日志和实际结果确认预期环境、编译器版本和工件。任务只建构时仅选择明确的构建目标；上传与调试按各自技能。

交付工具/配置、执行状态、日志定位与已验证的工件路径。已有项目钩子可能写文件或访问网络。按[硬件操作权限](../hardware/references/permission-gates.md)检查任务内允许的目录、启动影响及外发范围。

[官方命令文档](https://docs.platformio.org/en/stable/core/userguide/cmd_run.html)
