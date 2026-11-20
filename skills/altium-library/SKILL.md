---
name: altium-library
description: >-
  Create and verify Altium schematic symbols (.SchLib) and PCB footprints (.PcbLib) from datasheets and 2D drawings, as code. Use whenever a part library must be made, fixed, measured from a drawing, or checked. Triggers: "make a footprint", "create a symbol", "add this part to the library", "SchLib", "PcbLib", "footprint", "schematic symbol", "pad coordinates", "pin mapping", "verify this library", or being handed a component drawing and asked to turn it into a library — even if Altium is not named. 한국어: Altium 심볼(.SchLib)·풋프린트(.PcbLib) 라이브러리를 코드로 만들고 검증하는 절차. "풋프린트 만들어", "심볼 만들어", "라이브러리 추가", "커넥터/IC 라이브러리", "패드 좌표", "핀 배치", "Altium 라이브러리 검증", 부품 도면을 주면서 "이거 라이브러리로 만들어줘" 라고 하면 이 스킬이다. 검증만 요청받은 경우에도 쓴다.
---

# Altium 라이브러리 제작·검증

正式替换先据 [工程决策](../hardware/references/design-workflow.md) 的影响面核实际脚位、焊盘、热和装配。交精确 MPN、库件哈希与厂家原页，既有只读和原库写入门禁适用。

## 本机 Codex 路由：磁盘文件优先

凡是已有的 `.SchLib` / `.PcbLib` 文件，默认使用 `altium-offline-library` 的 `read_schlib`、`read_pcblib`、`validate_library`、`diff_libraries`、`render_symbol` / `render_footprint`。写库用用户指定的副本，写后重新读取。详见同级 [component-sourcing](../component-sourcing/SKILL.md) 的离线路径。

正文中涉及 `altium-mcp`、`eda-agent`、Altium 截图或 Models 面板的步骤属于可选的原生验收，仅在当前任务明确需要操作 AD 时执行。常规库操作和核对止于保存文件的验证，并标明证据来源。Python 文件工具使用装有 `altium-monkey` 的 Python 3.12，可复用本机 `components` 的虚拟环境。

## 建库顺序

1. 用完整订购型号、封装图号、原厂 pin 表和建议焊盘图确定目标。用 `scripts/survey_library.py` 盘点保存库，选基准件做逐脚对照。
2. 用 `scripts/measure_drawing.py` 取矢量尺寸，确定焊盘、孔、裸焊盘、Pin 1、视向和单位。用 `scripts/fit_symbol_body.py` 检查引脚和图形。
3. 在指定副本写入，用 `scripts/diff_symbol.py`、离线重读和渲染比对 pin–pad 映射、尺寸、可连接性、模型方向。需要写共享库、现场桥接或前台验收时按硬件门禁执行。

完整制作步骤、STEP 附着、验证清单和工具签名见 [建库操作参考](references/library-construction.md)。
