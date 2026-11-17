---
name: serial-shell
description: '在核实串口 CLI 和实际设备后执行指定命令，记录原始输入输出和状态。'
---

# 串口 Shell

优先分析已保存的交互日志。现场使用时核对端口、板卡、波特率、Shell 类型与结束符。确认设备启动提示和命令回显。打开串口前确认 DTR/RTS 和复位引脚关系。

向目标发送字节属于独立操作。按[硬件操作权限](../hardware/references/permission-gates.md)明确具体命令、是否改状态、预期响应和停止时间。逐条发送已认可的请求，验证响应再决定下一步。执行会更改设备状态的命令时先准备实际回退方法。交付原始字节、解码结果和结束状态。

[pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
