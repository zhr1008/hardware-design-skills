---
name: build-idf
description: '用 ESP-IDF 构建指定工程，并核对芯片、分区及生成工件。'
---

# ESP-IDF 构建

通过选定 SDK 的命令行环境确认 `idf.py --version`。核查工程根、计划芯片、`sdkconfig`、组件锁和分区表。已有芯片配置需变更时明确影响。

按所需生成目录执行 `idf.py -B BUILD_DIR build`。检查编译、链接和 flash 参数输出，记录 app、bootloader、partition table 与地址来源。

交付工具/配置、执行状态、日志定位与已验证的工件路径。已有项目钩子可能写文件或访问网络。按[硬件操作权限](../hardware/references/permission-gates.md)检查任务内允许的目录、启动影响及外发范围。

[官方命令文档](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/idf-py.html)
