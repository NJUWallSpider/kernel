# Kernel：论文成果证据稿

这份稿件整理整个 Kernel 项目的正面成果，供最终论文准备报告合并；它不宣告用户总目标完成，也不是一次新实验。条目 K01–K12 的精确指标、版本、复现入口、边界和 35 份本地资料的 SHA-256 见 [kernel-positive-evidence.json](kernel-positive-evidence.json)。本稿只读既有资料，没有执行测试、构建、Kernel、求解器、基准或 Agent，没有重新解析大型模型、证明或验收总账。

可以支撑论文主线的结果是：**项目实现了一个面向 MILP reformulation 的精确证明检查核心，将作者给定的完整模型关系与具体推导分离；除了仿射映射，还支持带联合存在条件的构造式恢复，并以原始合同审查、实际模型验收、独立精确算术与字节测试，以及限定条件下的性能实验提供证据。** 这里的贡献表述不包含文献中的优先权或首创性比较。

## 可直接使用的 12 项主张

**K01：统一的精确 MILP 语义与实际格式入口。** 模型坐标取实数，整数性由声明限定；行、边界、目标系数及常数用精确有理数计算。可信 MPS/LP 入口将支持的格式子集规范到同一 MCM 模型，包括完整 MAX 目标的符号转换，不依赖浮点容差接受证明。历史 MPS 扫描完成 **159/159 文件**的规范化；三个实际 LP 模型由独立的 stdlib Fraction 解析器与独立 MCM 解码器交叉核对，另有 **160 个生成 LP 模型**。这说明实际格式可进入同一精确检查流程；它没有覆盖所有厂商扩展，合法数学输入也可能因资源政策被拒绝。[MPS 规范](../../docs/MPS_V1.md)、[LP 规范](../../docs/LP_V1.md)、[语义](../../docs/SEMANTICS.md)

**K02：证明对象绑定完整、可区分的关系合同。** 调用者单独提供有序 Request，证书必须逐字段匹配。Kernel 从实际完整输出模型产生每个 Return 的所有边界、整数性、行、目标关系及观测义务；作者不能通过省略难证明的输出坐标或行来缩小合同。每个终端是一组同时成立的完整输出坐标，穷尽分支可以给出不同坐标组。MI/LP 输入输出域、Equal/NonIncreasing/None 目标、投影、逆映射、条件域和更强的双射是独立合同，不能由较弱合同自动升级。这是论文中比单纯“验证成功”更重要的接受条件。[语义](../../docs/SEMANTICS.md)、[原始合同审查](../DELIVERY_LEDGER_REVIEW.md)

**K03：五类具有联合存在论证的构造式恢复。** Flow、Interval、Menu、Signed、Subflow 五类规则使证明不局限于一条原坐标上的仿射逆映射。规则先在父作用域验证作者给定的全部前提，再扩展一组联合可行的新坐标，保留原模型前缀与目标。已有独立精确有限检查包括 Flow 的 **97 fixtures / 186 groups**、Interval 的 **241 fixtures**、Menu 的 **241 fixtures 与 16,382 个二进制向量**、Subflow 的 **983 Fraction fixtures**；这些是不同用途的有效与无效控制，不能相加作为统一覆盖率。联合存在引理及其 native 实例化器属于 TCB，后续检查 Return 并不会让它们变成不可信代码。[信任边界审查](../LIFT_TRUST_REVIEW.md)、[Subflow 引理](../../docs/SUBFLOW_V10.md)、[生产审查](../SUBFLOW_PRODUCTION_REVIEW.md)

**K04：完整双射，以及互不混淆的 LP 严格性见证。** 完整单射性通过两个新鲜的实际输入域副本检查：完整前向像相等时，必须推出每个原始输入坐标相等，包括未观测的连续坐标；构造式逆向恢复可以分支或扩展。另有不同合同分别表达 LP 严格包含、固定观测后不存在任何输入补全，以及一个完整仿射像落在实际对侧 LP 域外。独立检查覆盖 **80 个单射模型 / 640 点对**、**120 个 fiber box cases**、**1,875 个 image oracle 点**。实际 test62 保留原 MI/双射合同，同时加入 **4,500 坐标完整 LP 点与 500 坐标实际像**的排除见证。像排除不等于 LP 包含，也不等于部分观测无补全。[完整双射](../../docs/MENU_V7.md)、[Fiber 合同](../../docs/FIBER_POINT_V6.md)、[像排除审查](../IMAGE_EXCLUSION_REVIEW.md)

**K05：可处理任意小连续改进的严格优化合同。** 对显式仿射谓词 `p>0`，证书构造同一完整实际域内严格更优的点。正有理数比例余量 `epsilon*p` 允许连续变量产生任意小的正改进，不强加不存在的统一最小间隔。结合 `p<=0` 上的完整条件对应，可以保留每个已达到最优点的指定坐标，而不假设最优值一定达到。独立检查有 **1,000 次完整 verifier 调用**；实际 test36 覆盖 **200 个连续 terminal、37,616 个保留观测与 529,636 个义务**。实际 test83 给出 **65,832 坐标**的改进组，同时处理 **61 个**被支配非负坐标，独立稀疏代换确认 **100 条原等式**保持不变，最小正节省为精确的 `161497/1000000`。连续网格检查不是对实数域的穷尽证明；一般正确性来自已陈述的规则论证与其可信实现。[严格改进审查](../STRICT_IMPROVEMENT_REVIEW.md)、[test36 完整审查](../TEST36_COMPLETE_REVIEW.md)

**K06：完整原始合同的 81 例交付，包含五项实质 scope 修复。** 历史交付最终完成 **81 个实际案例、83 次完整验证调用、11 类相互重叠的结构族**。test46 的三段是同一实际模型对上的三个独立完整 Request，不能靠跨文件状态凑出方向。更有价值的是验收没有停在“当前 Request 被接受”：独立审查发现并关闭了以下原始合同缺口。

| 案例 | 完成的原始性质 |
| --- | --- |
| test36 | 对全部连续 terminals 的严格排除，并给出零面上完整保留投影及逆向合同 |
| test46 | 两个 MI 目标/投影方向，以及 target→source 的 LP 方向 |
| test58 | MI 前向不增、逆向相等，使用一组联合需求受限子流见证 |
| test62 | 保留 MI/双射，并对实际完整 LP 点及其完整像检查实际对侧约束违反 |
| test83 | 任一被支配非负坐标为正时严格改进，同时保留先前方向合同 |

冷构建时的 **262 tests**、2026-10-14 freeze 的 **280 tests**、2026-10-15 当前集成套件的 **344 tests / 41 result groups / 0 failures** 是三个不同截止；344 包含后续 Compiler、authoring 和 CLI 测试。这些数字是回归覆盖，不是 344 个独立 soundness 定理。历史 81 例由已准备证明验收，不能称为 81 次 fresh Agent 自主发现。[最终交付](../FINAL_DELIVERY_REPORT.md)、[scope 审查](../DELIVERY_LEDGER_REVIEW.md)、[当前测试收据](../compiler-performance/C10-preflight-20261015/validation.json)

**K07：冻结的规范格式与独立字节实现。** **MCM v1、RPX v1–v10 已于 2026-10-14 冻结**，包含显式版本门限、规范有理数、排序稀疏表达式、非法标志/保留位及尾部字节拒绝。独立 Python struct/Fraction 实现直接写出 bytes，Rust 解码后精确验证并逐字节重编码；它不调用 Rust 编码器制造自洽 oracle。条件域 fixture 检查 **354 个截断、2,520 个非法 flag/reserved 变体**；组合 V10 fixture 另有 **386 个截断、5,601 个非法 flag/reserved 变体**。冻结的 **65 页手册**有 **39 项 CLI 检查**，包括 9 项 INVALID、3 项 RESOURCE_LIMIT 和规范字节回环。FINAL_DELIVERY_REPORT 的旧 draft/unfrozen 叙述早于 freeze，当前状态以较新 freeze 文档为准；freeze 是兼容性决定，不是实现机械化证明。[冻结决定与收据](../PROTOCOL_V9_V10_FREEZE.md)、[统一格式](../../docs/FORMAT.md)

**K08：保持相同证书任务的内存表示改进。** 历史 frozen-v3 的单项 A/B 将 Step 槽从 **208 B 降到 96 B**，23 个固定 workload 的模型、RPA、RPX、Request 和数学计数均相同，**207 timing + 69 独立 RSS 进程全部 VERIFIED**。history65536 的 peak RSS 中位数从 **53.25 降到 39.25 MiB（26.3%）**；实际 test88 从 **51.125 降到 43.219 MiB（15.5%）**。该结果只改变内存布局；它不意味着 RPX 变小、证明流式解码或普遍降低延迟，报告保留了小任务回退。[同字节表示实验](../../bench/BOXED_CASES_REPORT.md)

**K09：共享作用域消除已观测到的平方级事实复制。** 历史 frozen-v5 A/B 将父事实复制改为不可变祖先借用、局部定义及删除掩码，并继续计费实际查找 probes。在预先固定的 n=4096 copying-heavy 任务中，执行中位数从 **827.142 降到 6.517 ms，约 127×**；较广的 23-workload A/B **552 进程全部 VERIFIED**，实际 test88 为 **182.553→120.189 ms**。独立参考状态机核对 **127,072 次操作**。实际 test18 的原 RPX/MCM/Request 一字不变，在相同 work ceiling 下由 RESOURCE_LIMIT 变为 VERIFIED。旧失败不能作为成功运行时间的分母；127× 只归属于指定任务族，非分支任务存在约 3% 的回退。去掉复制后 work 数改变是实际计费对象改变，其他数学计数与字节保持一致。[共享作用域实验](../../bench/SHARED_SCOPE_REPORT.md)、[独立状态审查](../SHARED_SCOPE_REVIEW.md)

**K10：保持精确性及相同 work 的有理数优化。** 历史 frozen-v7 与仅含 denominator-one、±1、零项快捷路径的 prototype，在 **49 个固定 paired workload**上保持全部 artifact hashes 和完整数学统计相同；**882 timing + 294 RSS = 1,176 进程全部 VERIFIED**，49 个执行中位数均降低。实际 test57 为 **4,932.676→2,219.925 ms（55.0%）**，test65 为 **3,776.316→1,795.367 ms（52.5%）**。条件是 Apple M5、10 cores、16 GiB、macOS 26.6.2、rustc 1.96.0 locked release、warm files、fresh processes，重负载 worker 暂停，顺序窗口而非随机交错；报告保留全部样本和异常值。四个启动主导任务的 process 中位数回退，RSS 变化在 3% 内。测得的 prototype 与后来的生产 binary 不能混用；后续 V10 回归报告也保留了真实变慢，不能把本项概括成所有版本全面加速。[有理数 A/B](../../bench/RATIONAL_SHORTCUTS_REPORT.md)、[独立复核](../rational_benchmark_review.md)、[后续回归](../../bench/V10_REGRESSION_REPORT.md)

**K11：高级完整合同已有分阶段绝对性能基线。** 历史 complete-v10 冷 binary `96a6d304…b9c8f8` 的独立窗口覆盖 **22 workloads、264 次验证/RSS 进程、63 次 synthetic preparation**。实际 test58 的完整合同检查执行中位数 **18.369 ms**、完整进程 **28.749 ms**、peak RSS **31.891 MiB**。n1024/g4 子流任务生成 **12,280 变量、16,376 行**，执行中位数 **56.732 ms**；完整作者准备为 **9,153.946 ms**，包含作者端简单的 O(nm) 构造，不能隐去。4096 坐标 strict-improvement、image-exclusion、halfspace 任务分别为 **2.046、2.294、4.646 ms** 执行中位数。它们是同一 host 上新能力的绝对基线，不是对不支持该能力的旧版本的 speedup ratio。[完整分阶段表与原始数据哈希](../../bench/NEXT_CAPABILITY_DRAFT_BASELINE.md)

**K12：Compiler 接入保留历史核心行为，并已有 fresh 实际使用。** Direct Certificate JSON→RPX 对全部 **81 例 / 83 pieces / RPX v1–v10**重现 byte-identical RPX；与独立构建的 pre-compiler `c16fdaf` 比较，**83/83 完整 Request 的全部 Statistics 一致**。累计处理 **4,090,495,643 B JSON 与 2,906,200,909 B RPX**。这是已作者给定证明的兼容性回放，不是自主证明发现；旧 RPA fixture 去掉 header 仅用于取测试数据，compiler 本身不经过 RPA parser/assembler。另有独立证据：C9 的八个不同已测输入（28、38、60、62、70、80、65、85）上，**8/8 fresh Compiler Agent 完成正式 Kernel 验证**，全部 16 个配对 arms 正常结束，保留完整源锚定与提交目标模型 readback；该轮使用 frozen539 包与旧 native5775，不能视作当前 API 的全量 fresh 验收。它证明实际可用的端到端完整合同，不证明任意改写都同样自然、无意愿偏差或与 Nomf 近似时间/质量。最终 C10 在本稿准备时仍在运行，结果未纳入。[pre-compiler 对照](../compiler-replay/README.md)、[机器汇总](../compiler-replay/summary.json)、[C9 正式验收记录](../compiler-agent/C9-summary.json)

## 论文叙述与复现边界

适合使用“精确检查”“caller-bound complete contracts”“经独立有限 oracle 与实际案例验收”“冻结的可互操作格式”等表述。证明层次应分别写清：文档中的数学 soundness/联合存在论证、这些规则的可信 Rust 实现、独立有限检查、完整实际模型执行、fresh Agent 的自主使用。当前没有 Lean 或其他形式化系统对整个 Rust 实现的机械化正确性证明；也没有据此宣称普适无错或对所有 MILP reformulation 的完备性。

核心 TCB 包含格式解析、精确算术、推导执行及 native 构造引理实例化。Python Compiler、作者脚本和 metadata 不构成证明权威。文件 SHA/manifest 负责定位实际输入与交付物；SHA 匹配本身不是数学证明。资源上限限制可执行范围，RESOURCE_LIMIT 不表示数学反例。

历史测量需恢复其 pinned source、Cargo.lock、binary 与本地忽略的大型模型/证明；部分历史 checkpoint/prototype 目录在交付后清理，不能假装新克隆已包含所有测量输入。JSON 每项列出后续复现入口，已有 raw receipts 保留精确命令、样本、artifact hashes 和 host。新的复现必须用新 label/output，不覆盖历史证据。本次未执行这些命令。

当前主要功能 checkpoint 是 `982235835dfe3b6c5f74188cd68ef48008747f30`，preflight native SHA-256 为 `cf9941c2daf9ab1434090069cc5040f902229e7b2d6d56003bcb0d8568e09da1`。preflight 为 **344 Rust tests、158 Python 3.9 tests、158 Python 3.14 tests**，其完整 source hashes 以既有收据为准；这些 suite 是正确性检查，耗时不当作基准。最终论文应在 C10 结束并独立审计后追加该轮结果，保持历史 corpus、兼容性 replay 与 fresh Agent 三种证据的界线。
