# Kernel specifications and manual

- **Format authority:** [FORMAT.md](FORMAT.md), the single complete MCM 1 and
  RPX/RPA 1–10 wire, text and mathematical contract reference. All are frozen;
  V9/V10 were frozen on 2026-10-14 with unchanged bytes and acceptance conditions.
- [Freeze decision and validation baseline](../audit/PROTOCOL_V9_V10_FREEZE.md),
  [historical specifications](../audit/specification-history/README.md).
- Mathematical arguments: [scalar semantics](SEMANTICS_V1.md),
  [Flow](FLOW_V4.md), [Interval](INTERVAL_V5.md), [Menu and bijection](MENU_V7.md),
  [Subflow](SUBFLOW_V10.md), [points](POINT_V3.md), [complete fibers](FIBER_POINT_V6.md).
  Signed decomposition is fully specified and justified in [FORMAT](FORMAT.md#signedlift).
- Tutorials and interfaces: [RPA V1](RPA_V1.md), [API/CLI](API.md),
  trusted [MPS](MPS_V1.md) and [LP](LP_V1.md) dialects.
- Evidence: [complete delivery report](../audit/FINAL_DELIVERY_REPORT.md),
  [trust reviews](../audit/TRUST_REPORT.md), [current tools](../tools/README.md).
- [Compiler API demand](COMPILER_API_DEMAND.md) is analysis and proposed compiler
  design, with historical source citations; it does not extend the kernel ABI.

## RPA/RPX Kernel 中文规范手册

手册依据当前安全 Rust kernel 编写，MCM 1 与 RPA/RPX V1–V10 均已冻结。
格式及规则的统一规范为 FORMAT.md；中文手册保持完整规范参考的标准。

- 阅读版：[rpx-manual.pdf](rpx-manual.pdf)
- 主文件：[rpx-manual.tex](rpx-manual.tex)，[章节源文件](rpx/chapters/)
- [完整可运行示例](rpx/examples/)

需要 XeLaTeX、`ctex`、Fandol 字体与 `latexmk`；使用 TeX Live 随附字体，
不需要 shell escape。PDF 位于 `docs/rpx-manual.pdf`，中间产物在 `docs/.build/`。

```sh
make -C docs
cargo build -p kernel-core --release --locked
python3 tools/check_rpx_manual.py --kernel target/release/rpx
```

示例复核从完整 LP/RPA 原文生成临时 MCM/RPX，核验独立 request、字节往返和负例。
汇编成功与数学验证成功分别检查；模型摘要和外部求解器不能授权接受。

内容与维护标准覆盖数学模型及 caller contract、fact/scope 状态、全部指令及终结点、
联合扩展引理、严格 JSON RPA、逐字段 MCM/RPX、可信 MPS/LP 导入、API/CLI、
预算与诊断、完整双向示例、实际案例及性能证据、能力历史与可信边界。
规则或格式变化须同步手册、完整示例和版本记录，重建并检查 PDF。
不兼容变更须登记新版本；有限测试不替代实现的形式化证明。

十份 FORMAT increment 与重复的 CURRENT_FORMAT 已由 FORMAT.md 取代。
被旧 manifest 固定的三个文档原样归档，其他旧版可由 Git `1468f95` 取回；
原 manifest、历史验收与 checkpoint 数量保持其时点含义。
早前已删除的 FIBER_STRICTNESS_DESIGN、FLOW_PRUNE_DESIGN 提案可由 Git `bbeb994`
取回；当前相应能力见 [fiber](FIBER_POINT_V6.md) 和 [Subflow](SUBFLOW_V10.md)。
