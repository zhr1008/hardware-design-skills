# 台架结果批量核验

把同一块板与同一个固件镜像的一组测量结果，和明确指定的限值逐项比对。命令读取两份文件并输出 JSON。运行设备、采集数据和将设备结果用于整板放行分别由对应专项处理。

~~~powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py bench-check limits.json --measurements measurements.csv
~~~

独立调用专项时，使用已确认的本机文件路径。

~~~powershell
python -X utf8 skills/hardware-design-review/scripts/check_bench_results.py --limits limits.json --measurements measurements.csv
~~~

## 输入约定

限值 JSON 中，`limit_set_id` 标记本组限值的版次，`board_id` 标记实际板卡或样机，`hardware_revision` 标记硬件版次，`firmware_sha256` 是用于测试的固件镜像的 64 位十六进制 SHA-256。`tests` 以测试 ID 为键，每项含单位及至少一个边界，支持只给下限或上限。边界是含端点的十进制数，允许用 JSON 数字或数字字符串表示。单位须同字面匹配，`V` 与 `mV` 须先在有记录的转换步骤统一。

~~~json
{
  "schema_version": 1,
  "limit_set_id": "power-rail-review-r1",
  "board_id": "sample-board-01",
  "hardware_revision": "A2",
  "firmware_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "tests": {
    "rail_3v3": {"unit": "V", "min": "3.135", "max": "3.465"},
    "boot_time": {"unit": "ms", "max": 500}
  }
}
~~~

测量文件使用 UTF-8 CSV，可有 BOM。表头如下，每项限值对应一条记录。不同板号、固件版本、工况或重复轮次分别保留原始文件并独立核验。若测试计划确实定义多次采样的均值、峰值或其他计量值，先按该计划形成可复现的结果行并保留原始数据与计算依据。

~~~csv
test_id,value,unit,board_id,hardware_revision,firmware_sha256
rail_3v3,3.135,V,sample-board-01,A2,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
boot_time,497,ms,sample-board-01,A2,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
~~~

## 结果与交接

### 接收已保存的采集文件

保留仪器原始响应、采集批次、同次前导／缩放、探头与校准、带宽、测量时间窗口、板号和实际固件记录。PyVISA 的波形和 SCPI 响应先由已知仪器格式解码，明确窗口和聚合方法后形成单值记录。例如 DS1054Z 的 NORM 波形只能用于注明屏幕窗口的指标，详见 [VISA 波形证据](../../visa-debug/references/waveform-evidence.md)。

使用 python-can 已保存日志时，记录版本、格式、采集通道、时钟、筛选和统计口径。固定通道与标准／扩展 ID，按测试计划明确远程、错误及 FD 帧。格式丢失关键标记、时戳倒退或样本不足时保留缺项。通用日志或缺通道的 CSV 不据此证明多路台架量测。六列 CSV 保持原样，旁证绑定原始及派生 SHA-256、工况和提取方式。只有具体采集已具备对应证据时才作为实测交接。 [PyVISA](https://pyvisa.readthedocs.io/en/stable/introduction/rvalues.html) · [python-can 文件格式](https://python-can.readthedocs.io/en/stable/file_io.html)

| 状态 | 退出码 | 含义 |
| --- | --- | --- |
| `pass` | 0 | 声明的每个测试都有一条匹配身份和单位的记录，且全部位于限值内。 |
| `fail` | 1 | 至少一条有效测量超限。逐项保留其他缺项。 |
| `invalid` | 2 | 文件格式、限值、单位、重复记录、未知测试或身份无法用于有效判断。逐项结果保留已判定的超限与缺项。 |
| `missing` | 3 | 至少一个声明的测试缺少实测行，已提供的记录均有效且在限值内。 |

完整读取两份输入后，输出包含两份原始字节的 SHA-256、可解析的限值 ID 和板卡身份、逐项结果及行号。固件摘要与测量 CSV 的比较校验的是两份输入描述的一致性。交接前仍需保留固件构建记录、测量者或台架、校准信息、工况与原始数据，综合评审据此判断证据是否适用。分析异常时先回到原始记录，再交电路或固件专项提出修正和复验条件。

OpenHTF 把数值验收规格与测量绑定。Renode 支持将测试轮次、日志及失败现场单独留存。Zephyr Twister 把测试绑定到目标平台，并区分运行方式。这个脚本采用显式限值、对象绑定和离线判定，可读取上述工具经归一化后的测量。 [OpenHTF 测量模型](https://github.com/google/openhtf#measurement) · [Renode 测试](https://renode.readthedocs.io/en/latest/introduction/testing.html) · [Zephyr Twister](https://docs.zephyrproject.org/latest/develop/twister/index.html)
