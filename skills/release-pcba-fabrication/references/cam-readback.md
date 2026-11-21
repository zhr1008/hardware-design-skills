# Gerber 与 Excellon 独立读回

```powershell
python -X utf8 -B scripts/check_cam.py assets/cam-fixtures/board.json
```

[合成夹具](../assets/cam-fixtures/board.json)展示 `hardware-cam-input-v1` 合同。按发布包实际制程配置提供必需角色。每项绑定相对路径、原生格式、单位、文件字节摘要和独立预期的毫米外接边界。对 Excellon 另给孔与槽的计数。边界数值包含绘制笔宽或工具半径。

Gerbonara 读取显式映射的层，报告解析器版本、摘要、实测边界、孔槽计数与警告。底面方向、装配对账、供应商 DFM、轮廓闭合与钻孔电镀分类按专项复核。缺层、错单位、错几何、无效文件、摘要变化和解析器不可用均保留各自状态。

把读回结果与同版 [EDA 发布记录](eda-release-adapters.md)及[装配检查](assembly-check.md)一起引用。包络表示独立读回范围。发布清单仍冻结原始制包文件与相关审批记录。

[Gerbonara 文件接口](https://gerbolyze.gitlab.io/gerbonara/file-api.html)
从 KiBot 取得的制程文件同样按上述角色和摘要核验。保留实际导出配置、板源版次及变体。几何读回只覆盖所列图层、尺寸和孔槽。
