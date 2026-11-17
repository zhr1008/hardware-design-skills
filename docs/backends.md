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

## 外部工具接到哪一步

| 工程需求 | 可选入口与交接证据 |
| --- | --- |
| 重复生成 KiCad 原生检查和制造文件 | 先用 **KiCad CLI 或作业集** 固化输入、规则与输出。项目已经维护 **KiBot** 配置时，可复用其本地或 CI 流程，把同版 ERC/DRC、Gerber 和钻孔文件交给包内读回与制造检查。CLI 产出的原生 JSON 走 `kicad-report-check`。 [KiCad 9 作业集说明](https://www.kicad.org/blog/2025/02/Version-9.0.0-Released/) · [KiBot](https://github.com/INTI-CMNB/KiBot) |
| 独立检查 Gerber、钻孔和装配 | **Gerbonara** 可按已批准的本地路径查看制包副本，使用 `gerbonara meta <archive>` 读层映射和边界，用 `gerbonara render <archive> <output.svg>` 导出初步视图。核对自动识别的层名、实际外形和孔位。需要对照板面与位号时可用 **InteractiveHtmlBom**，只在用户要求装配可视化时生成。CSV 交给 `assembly-check`；实际方向、原点与贴装预览继续由专项复核。 [Gerbonara CLI](https://gerbolyze.gitlab.io/gerbonara/cli.html) · [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom) |
| 复现固件问题与读取台架结果 | 有已建好的目标模型时，可用 **Renode** 跑可复现的固件测试；Zephyr 项目可用 **Twister** 选目标及运行方式，运行前区分构建、模拟和实际设备。需要组织真实台架序列时按项目选 **OpenHTF**。保留原始日志、配置、镜像摘要和测试类型；具备明确限值的量测归一化为 `bench-check` 的输入。设备操作按台架权限。 [Renode 测试](https://renode.readthedocs.io/en/latest/introduction/testing.html) · [Zephyr Twister](https://docs.zephyrproject.org/latest/develop/twister/index.html) · [OpenHTF](https://github.com/google/openhtf) |

固定 CLI 直接处理符合格式的原始工程证据。外部工具按现有工程配置和当前目标挑选，生成的文件留在指定本地路径。运行前核对其版本、项目脚本、输出与权限。

许可证适用于各工具本身。项目文件、资产、凭据和宿主配置由安装者在自己的环境管理。
