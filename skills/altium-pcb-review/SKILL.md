---
name: altium-pcb-review
description: 只读审查 Altium Designer 的保存版或已获准现场板卡，核对连接、叠层、关键网、规则、机械装配和 DFM 证据。
---

# Altium 板级审查

涉及写入或派生制造工件时，按[保存态回读](../hardware/references/saved-design-readback.md)逐项核对同版真实工程及原生报告，记录回执、写入结果和实际覆盖。

工程审查承接 [风险与交接](../hardware/references/design-workflow.md)，输出当前板身份及可定位的网、层、回流和制造覆盖。保存态缺项先报告，升级仍须按权限。

确认目标 `.PcbDoc`、项目身份、版次和保存态，优先用现有磁盘文件、报告和原生导出建立证据。只盘点板文件时直接运行 [保存文件读取](../component-sourcing/scripts/inspect_saved.py)，需要图纸上下文时用 [保存工程批查](../altium-schematic-review/scripts/inspect_saved_project.py)。

1. 盘点层叠、板框、器件、焊盘、网络、走线与规则来源。把关键发现定位到层、网名、位号、坐标或规则。
2. 结合用途检查回流、去耦路径、敏感模拟与干扰源隔离、载流和保护、板边及安装孔、连接器方向、装配与可测性。具体尺寸以实际板、制造合同和设备资料为准。
3. 使用已存在的 DRC 或已准许的定向读取时，核对规则、实际运行时间和覆盖。证据不够时单列需补查项。对原生编译、模态检查、现场桥接和 UI 按 [权限门禁](../hardware/references/permission-gates.md) 停在相应授权点。
4. 交付按严重性排列的问题、定位、证据和复核办法。规则或设计修复由板级实现专项承接并对照新旧版读回。
