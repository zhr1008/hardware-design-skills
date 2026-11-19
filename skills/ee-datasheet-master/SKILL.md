---
name: ee-datasheet-master
description: "Use when user has/is reading a component datasheet or spec sheet to find chip parameters: pinout, voltage, I2C address, timing, register map, electrical characteristics. Trigger on PDF+chip questions. Also: 规格书, 数据手册, 芯片参数. All IC types."
metadata:
  compatibility: "Python utilities require the packages listed in scripts/requirements.txt; available PDF readers may be used instead."
---

# EE Datasheet Master

For a hardware design, return the exact part, document revision/page, operating
conditions and min/typ/max distinction with each extracted fact. Bind decisions
to the hardware/firmware contract and reusable-reference record when available.
The bundled PDF utility is one execution path: another available PDF reader may
provide equivalent source evidence. Missing Python dependencies block that utility,
not all supported document-reading work. Never substitute memory for unread data.

## 读取与交接

字段语义及文件格式见[器件事实合同](references/component-facts.md)。

以完整 MPN、封装、PDF 版次及物理页为依据。单项参数直接定位表格、脚注和测试条件，区分保证值、典型值和绝对最大额定。未给出的关键字段保留 `unknown`，计算值附原文输入和推导。

需要正式交接时用 `scripts/validate_component_facts.py` 校验字段事实和 PDF 身份，再交电路、建库或采购资格专项。日常单点问题直接返回数值、条件、页码及缺项。

[按问题选取 PDF 步骤](PDF_STRATEGY.md) · [提取命令、疑难参数与排障](references/datasheet-extraction.md) · [完整分析模板](TEMPLATES.md)
