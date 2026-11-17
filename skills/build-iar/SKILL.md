---
name: build-iar
description: '从 IAR 工程选择配置，用 iarbuild 生成并核对目标镜像。'
---

# IAR Embedded Workbench 构建

使用匹配的 IAR 工具链与许可，检查 `.ewp` 中的配置名以及需要的变量路径。构建前核实项目自定义步骤。

以 `iarbuild PROJECT.ewp -make CONFIG -log all` 增量构建。只有显式要求重建时选相应模式。核对编译与链接状态、输出文件和链接映射。

交付工具/配置、执行状态、日志定位与已验证的工件路径。已有项目钩子可能写文件或访问网络。按[硬件操作权限](../hardware/references/permission-gates.md)检查任务内允许的目录、启动影响及外发范围。

[官方命令文档](https://wwwfiles.iar.com/arm/webic/doc/EWARM_IDEGuide.ENU.pdf)
