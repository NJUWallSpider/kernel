# Kernel specifications and manual

- **Format authority:** [FORMAT.md](FORMAT.md), the single complete MCM 1 and
  RPX/RPA 1–10 wire, text and mathematical contract reference. All are frozen;
  V9/V10 were frozen on 2026-10-14 with unchanged bytes and acceptance conditions.
- [Freeze decision and validation baseline](../audit/PROTOCOL_V9_V10_FREEZE.md),
  [historical specifications](../audit/specification-history/README.md).
- Mathematical arguments: [current semantics](SEMANTICS.md),
  [Flow](FLOW_V4.md), [Interval](INTERVAL_V5.md), [Menu and bijection](MENU_V7.md),
  [Subflow](SUBFLOW_V10.md), [points](POINT_V3.md), [complete fibers](FIBER_POINT_V6.md).
  Signed decomposition is fully specified and justified in [FORMAT](FORMAT.md#signedlift).
- Tutorials and interfaces: [readable RPA-S source](RPA_SOURCE.md),
  [JSON RPA V1–V10](RPA.md), [API/CLI](API.md),
  trusted [MPS](MPS_V1.md) and [LP](LP_V1.md) dialects.
- Evidence: [complete delivery report](../audit/FINAL_DELIVERY_REPORT.md),
  [trust reviews](../audit/TRUST_REPORT.md), [current tools](../tools/README.md).
- [Compiler API demand](COMPILER_API_DEMAND.md) is analysis and proposed compiler
  design, with historical source citations; it does not extend the kernel ABI.

Feature-specific filenames such as FLOW_V4 and INTERVAL_V5 identify the first
version that introduced a supported rule, not an obsolete implementation.
MPS/LP and MCM remain version 1. Current semantics and text assembly are maintained
in the unversioned SEMANTICS.md and RPA.md; FORMAT.md defines every accepted version.

## Reading the current capabilities

| Topic | Current reference |
|---|---|
| Complete models, contracts, wire/text layouts and all version gates | [FORMAT.md](FORMAT.md) |
| Scalar rules, scope, joint maps and current semantic invariants | [SEMANTICS.md](SEMANTICS.md) |
| Readable proof authoring | [RPA_SOURCE.md](RPA_SOURCE.md) |
| Frozen JSON RPA and independent caller requests | [RPA.md](RPA.md) |
| Flow / interval / menu extensions and complete bijections | [Flow](FLOW_V4.md), [Interval](INTERVAL_V5.md), [Menu](MENU_V7.md) |
| Activated signed decomposition | [SignedLift](FORMAT.md#signedlift) |
| Feasibility, permutation strictness, fibers and affine image exclusion | [Points](POINT_V3.md), [Fibers](FIBER_POINT_V6.md), [complete point contract](FORMAT.md#complete-point-witnesses) |
| Objective-level / halfspace domains and inverse-domain closure | [Restricted domains](FORMAT.md#objective-level-and-halfspace-domains), [actual test80](../cases/test80/README.md) |
| Strict improvement and demand-bounded subflows | [Improvements](FORMAT.md#strict-improvements), [Subflow](SUBFLOW_V10.md) |

## RPA/RPX Kernel 中文规范手册

手册依据当前安全 Rust kernel 编写，MCM 1 与 RPA/RPX V1–V10 均已冻结。
格式及规则的统一规范为 FORMAT.md；中文手册保持完整规范参考的标准。

- 阅读版：[rpx-manual.pdf](rpx/rpx-manual.pdf)
- 主文件：[rpx-manual.tex](rpx/rpx-manual.tex)，[章节源文件](rpx/chapters/)
- [完整可运行示例](rpx/examples/)

需要 XeLaTeX、`ctex`、Fandol 字体与 `latexmk`；使用 TeX Live 随附字体，
不需要 shell escape。PDF 位于 `docs/rpx/rpx-manual.pdf`，中间产物在 `docs/rpx/.build/`。

```sh
make -C docs/rpx
cargo build -p kernel-core --release --locked
make -C docs/rpx check
```

示例复核从完整 LP/RPA 原文生成临时 MCM/RPX，核验独立 request、字节往返和负例。
汇编成功与数学验证成功分别检查；模型摘要和外部求解器不能授权接受。
`make -C docs/rpx check-links` 单独检查当前 Markdown 的本地文件与标题链接；
构建也先检查链接。修改规范说明后，Makefile 会重新检查并构建手册。

内容与维护标准覆盖数学模型及 caller contract、fact/scope 状态、全部指令及终结点、
联合扩展引理、严格 JSON RPA、逐字段 MCM/RPX、可信 MPS/LP 导入、API/CLI、
预算与诊断、完整双向示例、实际案例及性能证据、能力历史与可信边界。
规则或格式变化须同步手册、完整示例和版本记录，重建并检查 PDF。
不兼容变更须登记新版本；有限测试不替代实现的形式化证明。

十份 FORMAT increment 与重复的 CURRENT_FORMAT 已由 FORMAT.md 取代。
被旧 manifest 固定的三个文档原样归档，其他旧版可由 Git `1468f95` 取回；
原 manifest、历史验收与 checkpoint 数量保持其时点含义。
已实现能力的 Flow、Interval、Menu、objective-level 旧设计提案也已移出当前
文档目录；数学论证和实际案例见上表，原设计过程可由 Git 历史追溯。
历史测试数量、验收记录和 manifest 保留其原时点含义，不作为当前接口说明。
