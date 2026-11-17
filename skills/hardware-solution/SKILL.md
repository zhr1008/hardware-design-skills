---
name: hardware-solution
description: 将电子产品需求推进到可交付的电路、PCB、固件和验证证据。用于整板开发、软硬协同、基于参考设计的改版和跨阶段交付。
---

# 电子硬件系统设计

先确定这次的交付终点和约束。核对供电、接口、环境、尺寸、成本、产量和验收工况。改版任务先读取获授权的源和版次，列出需要保留的接口与已知问题。整板用一个主 EDA 平台。

| 阶段 | 进入条件和交付证据 |
| --- | --- |
| 可测需求和接口 | 用 `plan-electronic-product` 明确指标，把电源状态、引脚、连通、时序和故障边界写入接口记录。 |
| 方案与选型 | 需要参考设计时用 `hardware-project-library` 核实来源和适配范围。用 `component-sourcing` 支持具体选型，按假设、原厂证据和计算记录工程取舍。 |
| 电路与板级实现 | 用 `design-and-review-circuit` 做设计，通过目标平台生产可编辑源，读回连接后交 `pcb-layout-review` 处理板约束。 |
| 固件与台架 | 用 `embedded-firmware-design` 依据同版接口实现驱动与状态机。构建、烧录和采样按平台选择专项。 |
| 冻结或制造 | 需要资格状态时用 `qualify-pcba-sourcing`，制造资料用 `release-pcba-fabrication`，综合状态交 `hardware-design-review`。 |

单项任务直接进入对应阶段。用户要求项目实施时，按当前许可把可完成的阶段推进到实际文件与复核证据。每次切换阶段携带源、工件版次、接口变更、证据和未关闭事项。电路或固件变更影响前序结论时，由权威源修复，再更新下游文件和测试。按 [硬件操作分级](../hardware/references/permission-gates.md) 分别核对原工程、前台、设备、上传和下单权限。
