---
name: serial-monitor
description: '从已有 UART 或 USB 串口日志排查启动与通信，或在核对控制线后采集有界只收日志。'
---

# 串口监控

从已保存日志开始，根据复位标志、时间戳、字节边界和协议分段。若需实时采集，确认目标端口、设备、波特率、数据位、奇偶校验、停止位、流控、编码以及时限。

打开串口可能改变 DTR 或 RTS 并触发复位或进入 bootloader。按[硬件操作权限](../hardware/references/permission-gates.md)确认接线和控制线行为，选择已核实的只收方式。无法确认副作用时先取得本次授权。采集保留原始字节与起止时间，再单独解码和统计。到时关闭本次端口与写入文件。

[pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
