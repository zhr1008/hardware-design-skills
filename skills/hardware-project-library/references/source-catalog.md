# 从哪里获取成熟工程和设计依据

核对日期：2026-10-31。以下是查找入口和已核对示例，不是全部通过本机验证的模板。每次采用精确工程时重新检查版本、文件、许可和工况。公开网页不自动授予对公司项目外传的权限。

| 需求 | 优先入口 | 实际取得与核对 |
|---|---|---|
| 电源、充电、保护、系统方案 | [TI reference designs](https://www.ti.com/reference-designs/index.html)；已核对 [TIDA-010240](https://www.ti.com/tool/TIDA-010240) | Design guide、测试、原理图、BOM、Gerber/布局、固件；PDF 层图不是原生 PCB |
| 模拟、测量、信号链、充电 | [ADI reference designs](https://www.analog.com/en/resources/reference-designs.html)；[MAXREFDES1260](https://www.analog.com/en/resources/reference-designs/maxrefdes1260.html) | Circuits from the Lab/设计包、评估板、模型与测量条件；关注误差/噪声/负载范围 |
| ESP32 模组和产品 | [Espressif 技术资料](https://www.espressif.com/en/support/documents/technical-documents)、[硬件入口](https://developer.espressif.com/hardware/) | 对应型号开发板源文件、原理图/BOM/布局/贴装资料、官方 KiCad 库、硬件指南 |
| STM32 硬件和固件起点 | [ST 开发板与硬件工具](https://www.st.com/en/evaluation-tools.html)、[STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) | 选定板的原理图/CAD 和 MCU 对应 Cube package、.ioc、BSP、例程；生成配置必须匹配精确封装与板版本 |
| 代码化可复用模块 | [atopile/packages](https://github.com/atopile/packages) | .ato、依赖版本、reference/test/example 构建、布局资产；编译/检查与实物成熟度分开 |
| 已有开源板 | [GitHub](https://github.com/)、[OSHWHub](https://oshwhub.com/) | 按精确器件/功能 + schematic/PCB/native/测试检索；检查原生文件、历史、开放问题和文件级许可 |
| PCB 派生工程经验 | [Keitark/pcba-design-skills 案例](https://github.com/Keitark/pcba-design-skills/blob/main/docs/case-study-nescart.md) | 学习约束重映射、功能分区和复验方法；单个 NES 项目不能当成任意产品的验证 |
| EasyEDA 电路块 | 当前 `easyeda blocks ls/show/search` | 查看真实拓扑、parts 和 verification 全部维度；失败/未测项不因 ready/verified 标签消失 |
| 当前 eda-agent 基础块 | `design_list_circuit_blocks` 的当前签名 | 仅参数化基础拓扑，参数/库仍需绑定具体器件，不能当完整工程参考 |
| ESP-IDF/Zephyr 固件 | [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/index.html)、[Zephyr board porting](https://docs.zephyrproject.org/latest/hardware/porting/board_porting.html) | 先锁项目版本再查同版文档、board/SoC、devicetree/Kconfig和例程；stable/latest 会变化 |

推荐查找式：`精确芯片 reference design design files`、`功能 evaluation board schematic BOM test report`、`型号 kicad_sch kicad_pcb`。公司已有板按功能域/接口/供电/故障签名查本地库。

将成熟度拆开：来源可追溯 → 文件可打开 → 原理和选型核对 → 布局/制造检查 → 仿真 → 组装测试 → 量产反馈。不得把前一层自动当后一层。厂商已测参考也只证明它的原工况。
