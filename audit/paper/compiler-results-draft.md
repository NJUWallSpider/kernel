# Compiler 论文结果草稿（C10 结果前）

本稿汇总已有正面结果，并保留其证据边界；机器可查版本见 [compiler-positive-evidence.json](/Users/bhz/Code/kernel/audit/paper/compiler-positive-evidence.json)。Compiler 将作者给定的证明编译到现有 RPX，由 Kernel 决定实际 Request 是否成立。下列结果不构成“所有算例均达到 nomf 的时间与质量且探索意愿不下降”的总验收。

实验背景需要一并呈现：C1、C2 已有正式验证成功，但存在显著时间与质量差距；C3 test16 在 30 分钟内未交付证明；C4 的旧 strict harness 对链式交付真实报错，随后保留原结果并通过独立版本化 review 验证其 MI 链。后续 32/32 仅指连续成熟阶段 C5–C9，不代表全项目没有失败。

## 可用于论文的十项结论

1. **沿用现有证明对象与 wire format 的直接编译桥。** Python → Certificate JSON → RPX → Kernel，不经过 RPA，也不搜索证明。历史 81 个已验证算例的 83 个 proof piece 覆盖 RPX V1–V10：83/83 RPX 字节完全一致、完整 Request 通过、全部 Statistics 与明确的 pre-compiler `c16fdaf` 基线一致。累计处理 4.09 GB Certificate JSON 和 2.91 GB RPX；记录的编译/验证耗时分别为 36.87/128.41 s。额外 merged test46 的 432,885,906 B JSON 直接编译、完整三项契约与 1,105,551 个 obligations 通过。此项是兼容性回放，不是新 Agent 实验。 证据：[README.md](/Users/bhz/Code/kernel/audit/compiler-replay/README.md)、[summary.json](/Users/bhz/Code/kernel/audit/compiler-replay/summary.json)。

2. **可自然声明且精确回读的 Python API。** exact rational `Expr`、Model、带 scope 的 Fact、显式 obligation、deferred map、contract summary，使作者操作模型与证明对象；MCM streaming readback 保留 native 全字段。对同一 228,350 变量、126,512 行模型，old/stream 各 3 个交错 fresh process 的 load median 为 5.138/3.838 s；六次 Python MCM 重编码均等于 native oracle。该结果只衡量 load，不衡量 Agent 全流程。最新 C10 前检查为两套 Python 各 158 tests，以及包含非 Compiler 功能的整个 core 344 tests 通过。证据：[report.json](/Users/bhz/Code/kernel/audit/compiler-performance/model-load-stream-20261015/report.json)、[validation.json](/Users/bhz/Code/kernel/audit/compiler-performance/C10-preflight-20261015/validation.json)。

3. **构造性、整数和 staged 证明得到真实使用。** C6 test58 使用 SignedLift 与两个 MenuLift；C9 test60 用 1,254 个 menus 构造 13,550 个 one-hot 变量，完整 MI 双向 Equal maps 检查 51,192 个 obligations；C9 test62 用两段显式 chain、反向 IntervalLift 的 2,029 个生成变量和 30,888 branches，得到最终 460 个 observations 的 MI 双向 Equal 契约。无 LP 或全链 inverse 时明确不宣称这些性质。证据：[C6-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C6-summary.json)、[C9-test60-phase.json](/Users/bhz/Code/kernel/audit/compiler-agent/C9-test60-phase.json)、[C9-test62-phase.json](/Users/bhz/Code/kernel/audit/compiler-agent/C9-test62-phase.json)。

4. **证明绑定实际输入和完整提交模型。** C9 八条 Compiler 交付均通过 trusted pristine source anchor、每段自身 canonical indices 的 native 检查，以及对最终标准模型所有变量、界、整数域、行和目标的 exact named 比较；test62 额外验证 stage join 和作者声明的 claim paths。此严格性只按版本记录适用，不倒灌为早期轮次的原始保障。证据：[C9-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C9-summary.json)、[verify_staged_agent_delivery.py](/Users/bhz/Code/kernel/tools/verify_staged_agent_delivery.py)；早期边界见 [C1-C3-input-integrity.json](/Users/bhz/Code/kernel/audit/compiler-agent/C1-C3-input-integrity.json)、[C4-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C4-summary.json)。

5. **连续成熟阶段的自主交付成功。** C5–C9 合计 32 次 Compiler 正式交付全部通过独立 formal 检查，并有 32 次 fresh nomf 对照。共涉及 14 个不同的既有已测算例：C5–C8 重复六题，C9 换八题。这里的 32 次不是 32 个独立算例，也不能推出未见算例族泛化。历史 83 pieces 回放、提供见证回归与 fresh Agent 的计数彼此分开。证据：[C5](/Users/bhz/Code/kernel/audit/compiler-agent/C5-summary.json)、[C6](/Users/bhz/Code/kernel/audit/compiler-agent/C6-summary.json)、[C7](/Users/bhz/Code/kernel/audit/compiler-agent/C7-summary.json)、[C8](/Users/bhz/Code/kernel/audit/compiler-agent/C8-summary.json)、[C9](/Users/bhz/Code/kernel/audit/compiler-agent/C9-summary.json)。

6. **完整轮次的时间观察显示工作流改善，同时保留较慢结果。** 下表使用每轮全部 Compiler/nomf Agent wall time，避免拼接各轮最快算例。C6–C8 package 固定为 `231e6f4`，但 prompt 与数学选择、最终目标及声明契约不同，不能推断独立因果或同质质量。

| 轮次 | 配对数 | Compiler 总 wall (s) | nomf 总 wall (s) | 总时间比 | 配对比中位数 | 配对比范围 |
|---|---:|---:|---:|---:|---:|---:|
| C5 | 6 | 4582.558 | 2516.589 | 1.821 | 1.641 | 0.924–3.106 |
| C6 | 6 | 3141.919 | 2427.598 | 1.294 | 1.205 | 0.838–1.888 |
| C7 | 6 | 2106.979 | 2391.847 | 0.881 | 0.859 | 0.499–1.445 |
| C8 | 6 | 2163.575 | 2296.619 | 0.942 | 0.898 | 0.647–1.457 |
| C9 | 8 | 3435.519 | 3023.927 | 1.136 | 1.118 | 0.538–2.453 |

C6/C7/C8 首次完整验证后的剩余工作总计分别为 974.259/490.456/487.852 s，中位数为 147.239/83.210/81.425 s。这是可观察流程成本，不等于全部浪费，也不是 prompt 因果估计。C9 test70 仍为 858.989 s 对 350.247 s；C7 test16 仍有 200.008 s 的自写重复集合构造。C6 solver quality 未测，不能作为旧 prompt 的质量因果基线。证据：[C7-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C7-summary.json)、[C8-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C8-summary.json)、[C9-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C9-summary.json)。

7. **同一完整大证明上的 zero/alias helper 回归。** 固定 C8 test16 的原始见证顺序、目标、maps、四项 MI/LP Equal inverse 契约和每项 178,164 observations；两个 forward scope 各逐项检查 50,186 个零/固定/alias Eq 的 exact expression 与可见 scope。`zero_sum` + `rewrite_many` 的给定推导耗时单样本从 12.382 降到 4.614 s，完整执行 147.734/139.444 s；source/target/Request/committed MPS 字节一致，helper RPX 有意不同，但两者 native VERIFIED。同时 serialization/binding 从 41.637 增到 45.300 s，不能只报有利阶段。这是 provided-witness regression，不是 fresh Agent 提速。证据：[summary.json](/Users/bhz/Code/kernel/audit/compiler-performance/C8-test16-provided-witness-20261015/summary.json)。

8. **leaf encoder 在不改证明字节的条件下降低一次 serialization 成本。** 同一 test16 supplied helper proof，source、target、Certificate JSON、Request、RPX、committed MPS 六类产物全部字节一致，四项完整契约与 3,118,120 obligations、所有 native Statistics 相同。记录的 serialization/compile/whole-binding 为 45.300/17.499 s，完整执行 139.444/99.930 s。仅一次串行比较，非 serialization 阶段也变化，不能把全部 39.513 s 差归于 encoder；RSS 不作门槛。证据：[encoder-summary.json](/Users/bhz/Code/kernel/audit/compiler-performance/C8-test16-provided-witness-20261015/encoder-summary.json)。

9. **subset_bounds 以通用接口代替作者手写共享 DAG。** 仅展开同一作者选定 packing premise 与 subsets，不选 cover、不搜索证明。在完整 C9 test70 给定证明上，6,887 个 subset fact 的 expression/scope 与三项契约、完整 maps 均一致；114,694,805 B Certificate JSON 和 110,074,809 B RPX 与手写版字节相同，522,056 obligations 和所有 native stats 相同。helper 总耗时 144.158 s，手写 140.772 s；subset 推导 34.171/22.107 s。因此这是表达便利性的精确回归证据，不是 runtime speedup。helper 在 C9 冻结之后实现，不能记为 C9 的新鲜使用。证据：[comparison.json](/Users/bhz/Code/kernel/audit/compiler-performance/C9-test70-provided-witness-20261015/comparison.json)。

10. **存在同时得到完整正确性证据和有利优化结果的复杂实例。** 下面给出正面例子；必须连同全 cohort 的失败、tradeoff 与探索缺口呈现，不能外推整体优势。

| 实验 | 实际形式契约 | 有界质量结果 | 证据边界 |
|---|---|---|---|
| C5 test88 | MI forward NI / reverse Equal，176 observations | Compiler LP 227，source/nomf 27；Compiler MIP 14.509 s 证得 230，另两者 120 s limit | MIP 每项单样本；不是三重复中位数 |
| C8 test51 | MI Equal inverse pair + reverse LP Equal，Request points=0 | 额外 22 个 convex-pair dominance fixes；MIP median 0.453/0.708 s，均 −3；LP −3.9755/−4.9593 | 绝对 MIP 差仅 0.255 s；author explicit point smoke 不在 Kernel Request |
| C9 test38 | MI Equal inverse pair + reverse LP Equal | MIP 单样本 53.688/62.736 s，均报告 Optimal、目标 204.081749241；LP 96.6779/82.6197 | proportional-sharing 候选另有 197 个 reconstruction 界未完成 |

这些例子之外，C9 test85 的 Compiler LP solve median 20.396 s 慢于 nomf 12.941 s；test70 三者 MIP 均在 presolve 时间限制且没有 incumbent。C8 test58 较快的求解并不能抵消遗漏 Signed/series 探索的事实。solver 数值接近或目标相同不承担正确性证明职责；正确性来自实际 RPX/Request 和 whole-model binding。证据：[C5-summary.json](/Users/bhz/Code/kernel/audit/compiler-agent/C5-summary.json)、[C8-quality-review.json](/Users/bhz/Code/kernel/audit/compiler-agent/C8-quality-review.json)、[C9-quality-review.json](/Users/bhz/Code/kernel/audit/compiler-agent/C9-quality-review.json)。

## 可复现性与截止边界

机器记录对每项列出版本、精确指标、primary local files 的 SHA-256 与复现命令。历史回放和固定见证脚本会使用保留目录，复现时必须使用独立 checkout/output，不能覆盖现有证据。fresh Agent 可复现的是设置与独立核验流程，数学选择和时间本身具有随机性。

当前最后一轮 C10（test70/38/58/55/69）使用 source `9822358`、native `cf9941c2…`；本文只登记 pending，不读取 live 数学或计入成功率。C10 冻结后新增文档不能当成其输入。依用户边界，完成这一轮后整理文档停工，不继续新增 fresh 轮次。整个项目的 near-nomf 时间、质量与表达意愿联合验收仍未建立。

资源项仅解释工程失败：新版本 JSON compile 默认预算 1 GiB、可显式配置；这不放宽后续 RPX/verify 的独立 caps，也不能把资源拒绝解释为数学命题为假。内存不作论文验收门槛。

本稿的 Kernel 测试和 native receipts 用于支撑 Compiler 集成；Kernel 本身的项目级贡献由主报告另行汇总。
