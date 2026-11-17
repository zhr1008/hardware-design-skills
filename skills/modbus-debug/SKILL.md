---
name: modbus-debug
description: '分析 Modbus RTU 或 TCP 抓包，或在明确授权后执行指定站点和寄存器的通信。'
---

# Modbus 诊断

从已有抓包分析端口或连接、站号、RTU CRC 或 TCP 事务、功能码、响应与异常码。建立手册逻辑地址和协议零基址之间的映射，记录字节序、字序、缩放与单位。

实时读取也会发出请求。按[硬件操作权限](../hardware/references/permission-gates.md)明确目标、端口、RTU 波特率与采样范围、寄存器、功能码、轮询速度和停止条件。写寄存器前还要明确旧值、写入意图及回退范围。若证据不足，交付抓包解析与拟执行请求的地址/功能码核对，等候当前许可。

[Modbus 官方规格入口](https://www.modbus.org/modbus-specifications)
