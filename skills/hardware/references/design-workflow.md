# 工程决策、证据与交接

由 `$hardware` 持有工程决定和交付验收。专项持有实际工程方法和工具结果，`hardware-solution` 管理整板接口，`manage-pcba-program` 管理项目阶段与签核记录。继续执行时复用仍适用的同版证据。

## 按目标启动

| 模式 | 工程动作与停点 |
| --- | --- |
| `plan` | 划定需求、功耗/热/电气预算、状态和接口，比较可执行方案。只要求规划时以可测需求、工况、责任和验收条件交付。 |
| `design` | 识别非理想及故障场景，比较方案、验算、实施所需工件，按实际交付读回。 |
| `review` | 先看风险后果和报告覆盖，再查实际网、层、封装、状态或几何。给出定位、证据、改进及放行范围。 |
| `eco` | 比对受控基线与方案，发现跨域影响，确定仍可复用的证明，修正权威源并重验。 |
| `verify` | 核型号、模型、激励、工况、测点、参考面、步长与限值。将求解成功和目标验证分别记录。 |
| `bringup` | 区分物理失效、测量伪影与固件解释。先用现有波形/配置/日志，记录证伪条件并设计最小隔离实验。 |
| `release` | 区分冻结制造包、供应商预检、阶段首件及批量，核同版、变体、工艺与 DFT，按目标确认工程资格和签核。 |

日常设计、需要展开风险的局部审查、选型判断和排障在技能目录用轻量参数启动。

```powershell
python -X utf8 -B scripts/design_flow.py start design --intent "24 V 供电的 MCU 精密采样前端"
python -X utf8 -B scripts/design_flow.py start design --prototype adc-front-end --prototype ldo
python -X utf8 -B scripts/design_flow.py start bringup --prototype switching-power --model-limit measurement-conflict
python -X utf8 -B scripts/design_flow.py prototypes
python -X utf8 -B scripts/design_flow.py basis --rule adc-antialias-budget --rule analog-capacitive-load
```

- `--intent` 匹配有界的原型别名，允许多项命中。确认实际功能块，用 `--prototype` 补没有识别的原型，按项目条件筛去不适用的候选；如果原型不明，先识别接口、能量、状态和工作范围。原型默认展开风险包，即使用户未提具体失效。读取 `required_checks`、`required_rules` 和相应参考页，不把所匹配的规则当作结果。可以加旧参数 `--topic/--rule` 扩展候选。
- `basis` 批量读取选定规则和去重来源页，核身份及版本摘要。 `retrieved` 是已转换且返回的正文，`partial` 可用原 `knowledge.py read ... --offset ...` 读更多。公式、原图或 OCR 可疑时核允许读取的原页。公开包可用 `--library` 读取用户的本机正文库。只拿到规则或索引就注明缺原文，不用新版页码补旧版。
- 输入已明确的精确查料、按接线画图、原生报告读取、单点计算和转档直接调用既有入口。这些操作无需项目追踪或 case。工程验算复用[现有模型与退出码](model-checks.md)，[批处理](local-tools.md)保留既有行为。

### 低风险局部参数微调

既有拓扑和用途明确，只调普通指示灯限流、上下拉或简单分压，且改动不牵涉功率换流、高速或射频、绝缘安全、热瓶颈、关键换层回流时，直接定量核算。给改前/改后值、计算条件、最坏工况及决定是否可用的器件边界。比如 LED 核导通电流、阻值功耗、GPIO 带载电平与单脚/端口电流；分压核容差、负载和接收端允许范围。题面缺具体型号时保留条件结论。

上述检查已能支持当前答复时就收口。若缺项会改变结论，优先一次定向查数据手册、项目限值或现有测量。遇到快边沿或采样建立、热或安全边界被触及、拓扑/工况改变、正式 ECO 或放行时，按相应工程流程展开并保留证据。

## 把工程规则带到后续环节

`start` 展开当前模式的 `required_checks`、规则 ID 和 `phase_action`。对运放容性负载、快边沿端接和屏蔽共模路径，先确认对象和条件，再把对应动作落实到该阶段的产物。对话中给出“哪个工况、哪个节点、怎样判定、还缺什么”即可。正式交接保留原检查 ID，沿用同版证据或将检查记为 `open`。即使交接后的任务描述很短，`start` 与 `assess` 也会保留正式记录里已有的这类检查；没有关闭证据时返回待证。

| 工程判断 | 规划与设计、审查 | ECO、验证、排障与放行 |
| --- | --- | --- |
| 运放带容性负载 | 同时分配稳定裕量和接收端建立时间。比较直驱与补偿，标出反馈取样点和接收端测点。 | 放大器、反馈网络、负载寄生或采样设置变更时重验。核环路和实际接收点，冻结配置与有效证据对应。 |
| 快边沿端接 | 依据边沿、拓扑和飞行时间建模。源端端接适用时核近源位置、驱动阻抗和接收点。 | 叠层、布线或固件驱动设置变化时重验。按接收端门限和时序验证，冻结版维持经验证的叠层和端接。 |
| 线缆屏蔽与共模路径 | 分别画各注入点的电流回路，确定外壳搭接、保护地约束、受扰点及验证工况。 | 连接件、机壳、线束或夹具变动时查受影响工况。对照测量后返回基线复验，记录正式报告实际覆盖的端口。 |

`impact` 从已适用或已记录的检查传播变更，按变体区分失效和可复用证据。手算筛选与正式关闭条件按项目限值和实测需求确定。原文页、规则摘要或 ERC/DRC 报告按各自实际证明范围使用。

### 高风险分支与阶段证据

同一检查只给一个工程结论。适用分支作为该检查下的 `branches` 返回，内含本阶段动作、最低证据、硬红线、允许的原型步骤及经核版本的页码。例如功率路径可以同时核 P2 换流、P3 限流窗口及 B2 局部铜孔瓶颈。关闭时在同一条记录中覆盖适用分支，保留分支各自的量测或模型条件。

| 父检查 | 分支及其启用条件 |
| --- | --- |
| `power-stability` | P1 适用于开关稳压环路。MLCC 替代先识别位号用途，影响环路时沿 `effective-capacitance` 回开 P1 及对应的频响和模式切换验证。 |
| `power-path` | P2 限功率开关级、高速高应力换流、高储能切换或保护重试。P3 核限流阈值、消隐和延迟与热态磁件。B2 核大电流过孔、窄颈和接端的制成品下界。 |
| `thermal` | T1 核有意义的实际装机结温和测温偏差。T2 只管电解、固态及混合电容系列的纹波与寿命。T3 与 P2 共用功率场景边界，另核重复脉冲的结温和 SOA。 |
| `return-path` | B1 核关键路径的同网参考、异电位参考和隔离边界。叠层改变后从实际铜图回查，按需要补接收端或共模证据。 |
| `production-evidence` | B3 在 SMT 放行、装配首件及钢网、锡膏、拼板或产线变更 ECO 下启用。裸板 `fabrication`、原理图和手焊原型沿原有路径。使用 `--target smt_release` 明确装配放行范围。 |
| `fault-propagation`、`power-states` | R1 核保护泄放和后续供能，R2 核反接、反灌及掉电矩阵，R3 从隔离接口追到最终安全输出和恢复授权。绝缘要求仍由 `insulation` 独立验证。 |

先确认 `scope_candidate` 所指工况。正式记录用 `facts` 携带分支编号及 `present/absent/unknown`，并在审查说明里记录处置依据。角色、物料类别或器件应力尚未明确时用 `unknown`。P2/T3、T2 和 B3 仍需分别命中已知功率工况、适用电容类别或装配范围，单独填 `unknown` 不设门禁。核实不适用才填 `absent`；它可取消关键词推断，明确的 `smt_release` 或 `first_article` 仍保留 B3。用 `basis --branch B1 --branch R1` 回读资料，并用原图核参考面及保护元件相对位置。普通低速开关、精确查料、单项计算和既定接线绘图按原短路径处理。

## 模型升级与反证

- **先查决定性非理想项。** 常规容差、温漂、实际 C、额定、上/掉电、棕断、负载瞬态、单点故障及实际回流按适用范围核。用[11 域索引](lifecycle-domain-index.md)获取公式、规则和原始出处。条件相关的角点必须确证可达。
- **在决定前反证。** 记录“最严重或可能失效 → 工况/依赖 → 能推翻当前假设的观察 → 验收或回退”。审查从隐患机理查对象，不用 ERC/DRC 零报告代替覆盖。排障对照假设时核探头地、量程、共模/时间基准、定标、加载与环境；归因需对照和原始工况复验。
- **手算何时够用。** 明确感兴趣的量，模型线性、有界，已知保证值和足够余量时可关闭该项。一阶模型作为筛选时记录适用范围。典型值或保守跨限时补保证参数、相关性与可达角点。已证越界便处理失败，证不到的边界保留待验证。
- **何时升级。** 器件动态或保护切换能改变决定时用覆盖相应行为的宏模型或实测。寄生或装配主导时引入实际几何和返回路径。实物验收、测量矛盾或模型不覆盖的关键行为有可复现台架证据才关闭。轻量入口的 `--model-limit` 给下一步，正式 case 可按检查记录 `model_limits`。设备实施仍核[权限门禁](permission-gates.md)。
- **务实推进。** 硬红线包括适用安全条款、器件绝对额定、不可逆单点故障、明确制造硬冲突。无法验证高后果假设先限制该决定。普通未知则给有界暂定工况、可调整规格和首板关闭方法。优先能普遍采购的封装和易搭接二供；保留确有用途的测试点、可断开 0Ω、隔离跳线、滤波/吸收选装位，同时核走线、安全间距、测试加载和可生产性。避免无益的冗余或堆料。

## 正式工件与停点

正式评审、跨阶段交接、正式 ECO 和制造放行保存 `case.json` 并执行完整 `assess`。根入口、专项和状态脚本按同版及许可消费结果。局部任务自然完成所需工件即可。

```powershell
python -X utf8 -B scripts/design_flow.py start eco --case ./case.json
python -X utf8 -B scripts/design_flow.py impact --case ./case.json --change ./eco.json
python -X utf8 -B scripts/design_flow.py assess --case ./case.json --target formal_eco --root .
```

1. 按[工程记录 schema](../assets/engineering-case.schema.json)填 `mode`，冻结 `baseline.project/revision/variant`。用 `artifacts` 记录仅与当前决定有关的实际文件路径和小写 SHA-256，`facts` 按风险 ID 记录 `present/absent/unknown`。已由模式或原型触发的项不能靠 `absent` 删掉。用 `start` 查阶段和范围。
2. `checks` 按检查 ID 记录 `open/pass/fail/not_applicable`，结论包含 `condition`、`criterion`、`finding`、需要的 `artifacts` ID 和 `evidence` ID。引用证据必须定位至[现有包络](evidence-and-backends.md)和真实输出哈希。 `not_applicable` 需要可核的适用性结果。
3. 实际工程复核完成后，可用 `bind --case CASE --evidence INPUT --check CHECK --execution EXECUTED --condition CONDITION --criterion LIMIT [--disposition STATUS]` 给原包络单独输出范围绑定。将输出保存为新证据文件并计算哈希，注册至 case 的 `evidence`。一个回执可逐项补绑定；只有原工具已执行且证据层达到要求的项能绑定。绑定和哈希校验证明记录适用边界与一致性，仍需工程人员审查实质内容和签核。
4. `assess` 支持 `formal_review / handoff / formal_eco / fabrication / evt / dvt / pvt / first_article / smt_release / production`。EVT/DVT 用验证或 Bring-up，PVT、首件与量产用放行。它核对象、版次、变体、工况、判据、实际执行项、证据级别和摘要。退出码 0 为 `covered`，1 为已证违反 `blocked`，2 为 `needs_evidence` 或输入无效。未完成、报告无发现或旧文件不能关闭核验。检查限制在指定本机根目录。
5. **工程覆盖、项目签核、动作许可独立。** `covered` 不是签核或设备/上传授权。冻结工程包与供应商预览、首件、批量出货分别决定。项目记录按自己的批准来源校验，经授权才能登记。需要前台、发帧或仪器控制时仍按实际调用申请。

适用分支用 `bind --branch ID` 绑定到实际执行项，可重复指定同一执行覆盖的多个分支。每个父检查的证据集合需要覆盖其全部适用分支。B3 需要实际装配首件记录。EVT、DVT、PVT、首件、量产和 SMT 放行按所触发分支的证据层核验，模型与保存态材料可支持设计或 ECO 评审时的相应结论。已证违反仍按有效的失败证据处理。

`impact` 的变更文件使用 `hardware-engineering-change-v1`，含同一个 `baseline` 和 `changes` 列表。每条有 `kind`、`object`、`variant`、`before`、`after`。作用于所有变体才用 `*`。受控对象应具体到位号、网络、固件接口、工艺或供货池。钢网、锡膏、拼板或产线变更使用 `assembly-process`。输出检查依赖路径、分支重验、基线失效项及待核的复用候选。复用时比对原稿、工况和适用范围；改动权威源后重跑受影响项。现有阶段机制可用 `program_state.py invalidate-impact` 在明确授权时消费同一工程基线。

## 专项接力

给专项传工程要求、风险、输入身份、目标产物、判据、许可和停点。专项交回实际工件、证据引用、失败或未覆盖项。无资料覆盖的部分继续取证或交已获结果。平台、EDA 会话、批处理和采购不自行决定全局放行。参见[跨专项交接及变更回流](route-matrix.md)。
