# BOM 批量工具

用 Python 运行 [bom_archive.py](../scripts/bom_archive.py)。省略 `--output` 时只读输入并返回预检 JSON。明确产物路径时，一次完成 V1 字段映射、按证据补 C 号、写入 UTF-8 BOM/CRLF CSV 并读回逐格核对。工具写入新文件，目标已存在时会请求另选路径。CSV 使用 Python 标准库。XLSX 使用本机 `openpyxl`，多表时指定 `--sheet`。

```powershell
python -X utf8 scripts/bom_archive.py BOM.csv
python -X utf8 scripts/bom_archive.py BOM.xlsx --sheet BOM --header-row 2 --output archive.csv
python -X utf8 scripts/bom_archive.py BOM.csv --column-map columns.json --evidence parts.json --output archive.csv
```

省略 `--template` 时读取随技能附带的 23 列 V1 模板。另有约定时传入以第一行为表头的 UTF-8 CSV。模板精确列名优先，其次匹配如 `MPN`、`Manufacturer`、`Package`、`Designator`、`Qty` 等常用源列。歧义时用 `--column-map` 显式绑定，例如 `{"型号":"原始订货号","规格":"初始规格"}`。只有明确要略过的列才在映射中填 `null`。工具会报告未使用的源列。已映射的 XLSX 公式、错误值和不能原样保留的日期要求先提供要归档的实际值。

位号、层级、数量、原有料号及人工业务信息保留原值和顺序。V1 将独立的 DNP 和变体附在同一行的备注。格式如 `0000` 的整数按 XLSX 显示保留前缀，数字 `603` 若已失去前导零则原样保留并标记核对。数量及层级取自源数据。预检 JSON 按类型列出问题数量，`--details` 可看全部行号。

源 BOM 未给状态列时，V1 对未标为不贴装的记录使用 `启用`。DNP 的显式否值（如 `FALSE`、`0`、`No`、`否`）在备注保留原样，仍按贴装记录填写默认状态。其他非空 DNP 标记保留供复核，状态留空。

单元格仅含「待核实」「待核查」「待核对」「待确认」「未录入」「未标注」时按空项处理。描述中半角 `/` 分隔的独立占位段也会清除，含网址或其他自由文本的混合描述交付前需人工检查。清除占位的行号和字段记入独立的 JSON 核查报告（`omitted_placeholder`）。人工复核时清除备注中的操作过程和核查话术，保留实际适用条件、配套件和有效商品链接。

可选的 `--evidence` 使用已核对的国内立创商品页资料。以下为结构示例，业务上需先核对来源：

```json
{
  "reviewed": true,
  "parts": [{"mpn":"DEMO-PART", "brand":"示例", "package":"0603", "lcsc_code":"C900000001", "product_url":"https://item.szlcsc.com/900000001.html"}]
}
```

只有 BOM 已有的完整型号、品牌及封装均精确匹配且 C 号唯一时，才填写空的 `MPN料号`。已有有效料号及其他供应商的业务信息原样保留。候选证据、参数化选型和有冲突的 C 号交器件专项，工具运行不联网。`status=verified` 表示归档文件可读且字段与本次映射一致，`issue_counts` 和 `issues` 供独立核查。
