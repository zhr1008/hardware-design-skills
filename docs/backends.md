# 可选运行依赖

使用前核对当前环境提供的工具名、版本、实际参数和用户权限。包内流程可使用宿主已有 MCP 或 CLI，按任务安装确实需要的依赖。

| 任务 | 可选依赖 |
| --- | --- |
| 电路示意图 | Python 和 Schemdraw。校验脚本随 `draw-schemdraw-circuit` 安装。 |
| Altium 保存文件解析 | 支持当前工件的 `altium-monkey` Python 环境。库只读 MCP 可按需独立配置。 |
| 原生 EDA | Altium Designer、EasyEDA Pro 或 KiCad，及与目标平台匹配的 CLI/连接器。活动项目、写入和界面操作遵循对应授权。 |
| 器件查询和库转换 | 独立安装 [Component Sourcing MCP](https://github.com/zhr1008/component-sourcing-mcp) 并启用 `components`。批查脚本另外需要 MCP Python SDK。HTML/XLSX 选型导出使用标准库，BOM 的 XLSX 输入需要 openpyxl。 |
| 仿真 | 实际可用的 SPICE 求解器或用户指定的 Multisim 环境。按工作文件和求解器核对网表及模型，按工况读回波形。 |
| 固件与台架 | 用户项目指定的 SDK、编译器、调试器及仪器。随包 `workflow` 脚本生成离线步骤预览，实际构建和设备动作由对应专项按授权执行。 |
| 机械 | `lab-hardware-cad` 按需使用 build123d。用户也可使用自己的 SOLIDWORKS、FreeCAD 或对应 CAD 入口。原始 3D 文件与几何数据默认留在本机，外发需单独批准。 |
| 工厂流程 | 用户自己的嘉立创、Fictiv 或对应供应商入口。按文件版本、接收方、价格和用户授权分别处理预览、上传、报价、下单和付款。 |

许可证适用于各工具本身。项目文件、资产、凭据和宿主配置由安装者在自己的环境管理。
