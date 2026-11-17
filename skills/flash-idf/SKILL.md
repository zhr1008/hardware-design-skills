---
name: flash-idf
description: '按 ESP-IDF 实际烧录清单写入指定板，核对串口、地址与验证结果。'
---

# ESP-IDF 烧录

绑定芯片、目标板、串口、SDK 版本、生成目录和已核对 flash arguments。普通 `idf.py -B BUILD_DIR -p PORT flash` 会利用指定工程的构建数据并可能触发构建，按交付要求固定镜像与地址。

在烧录或可能重置设备前按[硬件操作权限](../hardware/references/permission-gates.md)确认目标、镜像摘要、地址和预期副作用。

检查实际烧录位置、写入及校验状态。将随后复位、运行日志与烧录证据分别记录。

[官方工具文档](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/idf-py.html)
