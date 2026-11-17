# BOM/CPL 位号核对

在同版导出后、冻结制造包前，将 UTF-8（可带 BOM）的逗号分隔 CSV 交给离线核对器。无需供应商账号、网络或额外 Python 依赖。

```powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py assembly-check BOM.csv --cpl CPL.csv
python -X utf8 skills/hardware/scripts/hardware_tool.py assembly-check BOM.csv --cpl CPL.csv --exclude "TP1,H1"
```

- BOM 支持 `Designator`、`Reference`、`References`、`Ref` 等位号列；单元格内可用逗号、分号或空白列出多个明确位号。范围应在导出时展开，KiCad BOM 支持将 `--ref-range-delimiter` 设为空字符串。
- CPL 每行一个位号，支持常见的 `Designator,Mid X,Mid Y,Layer,Rotation`、`Ref,PosX,PosY,Side,Rot` 和 `Ref Des,Mid X (mm),Mid Y (mm),Layer,Rotation`。脚本检查两侧位号缺漏和重复，检查层面、坐标和角度能否解读，并指出混用的显式坐标单位。支持在轴列头或坐标值声明 `mm`、`mil` 或 `in`。未声明的坐标单位标为 `unspecified`。
- BOM 的 `DNP` 等列仅接受常见的真假值。嘉立创 `Customer Supply` 列明确填 `DNP` 时也视为不贴装，与明确的 DNP 否值冲突时报告复核。对确实不贴装且在 BOM 中有位号的测试点、定位件或手焊件，可显式传 `--exclude`。被排除的位号仍出现在 CPL 时会报问题。
- 退出码 0 表示在这些检查范围内一致，1 表示有待修项，2 表示输入无效。默认 JSON 带两个输入 SHA-256、按板面计数和问题明细。将该结果关联到冻结版次。位号大小写统一后比较。

接着独立核验封装、引脚、原点、旋转方向、底面镜像和厂家贴装预览。发现方向差异时，先核对库和 PCB 放置，再检查导出坐标约定。修正源文件并重新生成对应的制造数据。表格核对只是其中一道检查。

参见 [嘉立创 BOM/CPL 常见差异](https://jlcpcb.com/help/article/common-bom-and-cpl-matching-issues-and-explanations)、[贴装坐标约定](https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly)和 [KiCad CLI](https://docs.kicad.org/9.0/en/cli/cli.html)。
