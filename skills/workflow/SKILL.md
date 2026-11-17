---
name: workflow
description: '安排明确请求的嵌入式构建、烧录、日志采集或调试步骤，提供本地离线预览与跨步骤工件记录。'
---

# 嵌入式工作流

把工程、工具链、构建配置、目标板、镜像、探针/端口和停止条件绑定到一次运行。预览脚本根据输入列出已知和缺少的条件，输出 JSON 至标准输出。

```powershell
python -X utf8 scripts/workflow_runner.py --build-system cmake --project ./firmware --target app
python -X utf8 scripts/workflow_runner.py --run build-flash-monitor --build-system platformio --project ./firmware --target example --flash-target example-board --flash-interface serial --port COM5 --baud 115200 --dry-run
```

单次构建直接进入相应构建技能。流水线按计划中已请求的步骤执行，每一步读回结果再决定能否继续。

1. 构建后核对目标、镜像存在性、字节数和 SHA-256。构建报错、目标不同或缺镜像就停在构建。
2. 烧录前核查板卡/芯片、接口、探针身份、地址与允许的擦除和复位范围。PlatformIO 等工具的上传目标可能先调用构建；明确镜像需要固定时核对项目支持的上传方式。
3. 对照镜像注明验证、复位与启动日志各自的状态。连接调试器可能暂停或改变目标，打开串口可能切换 DTR/RTS。继续前按[硬件操作权限](../hardware/references/permission-gates.md)核对具体许可。
4. 达到时间、日志条件或错误边界后关闭本次资源。交付镜像身份和每步实际结果。

脚本只读取指定工程、可选镜像的路径状态，且只输出计划。执行参数及证据以对应专项的工具契约为准。
