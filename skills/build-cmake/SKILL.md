---
name: build-cmake
description: '配置或构建 CMake 项目的指定目标，记录编译器、构建目录和生成工件。'
---

# CMake 构建

区分源码树和构建树。读取适用的 `CMakePresets.json`、交叉工具链和目标定义。复用同目标现有构建目录；调整工具链时使用明确的新目录以免混用缓存。

配置可用 `cmake -S SOURCE -B BUILD`，构建用 `cmake --build BUILD --target TARGET`。使用项目预设时依据项目定义选择；多配置生成器按需指定 `--config`。核对实际输出和目标。

交付工具/配置、执行状态、日志定位与已验证的工件路径。已有项目钩子可能写文件或访问网络。按[硬件操作权限](../hardware/references/permission-gates.md)检查任务内允许的目录、启动影响及外发范围。

[官方命令文档](https://cmake.org/cmake/help/latest/manual/cmake.1.html)
