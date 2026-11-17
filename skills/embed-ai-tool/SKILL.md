---
name: embed-ai-tool
description: '识别嵌入式工程的构建、烧录、调试和采集入口，适用于尚未确定工具链或存在多个板级配置。'
---

# 嵌入式工具链入口

从用户指定的根目录查项目标志。只有一个吻合且已有明确目标时，直接进入专项。工作区含多个示例、板卡或构建系统时，根据版本、实际构建文件和交付对象缩小范围。

| 工程依据 | 构建入口 |
| --- | --- |
| 指定 `.uvprojx` 或 `.uvproj` 与真实 target | [Keil](../build-keil/SKILL.md) |
| 指定 `.ewp` 与有效配置 | [IAR](../build-iar/SKILL.md) |
| ESP-IDF 的 CMake 项目及 SDK 环境 | [ESP-IDF](../build-idf/SKILL.md) |
| 工程 CMake 文件、工具链、预设或生成目录 | [CMake](../build-cmake/SKILL.md) |
| Makefile、自带规则和目标 | [Make](../build-makefile/SKILL.md) |
| `platformio.ini` 与环境名 | [PlatformIO](../build-platformio/SKILL.md) |

构建交付包含工具版本、目标、输出位置与实际工件。镜像名称相同而地址或版次不同时，以实际工件摘要和地址布局交接。单次构建在产物读回后停止。多个步骤用 [工作流](../workflow/SKILL.md) 预览，按[硬件操作权限](../hardware/references/permission-gates.md)核对各步骤许可。
