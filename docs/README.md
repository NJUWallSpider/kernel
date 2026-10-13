# Implemented kernel specifications

- **Start here:** [current complete wire/text reference and capability history](CURRENT_FORMAT.md).
  It consolidates frozen V1–V8 without introducing a new version; the implemented
  objective-level V9 draft is explicitly separated and remains unfrozen.
- **Compiler design input (not a spec):** [what the 81 corpus cases demand from the
  compiler layer](COMPILER_API_DEMAND.md) — per-case API needs with evidence from the
  domain-agent trajectories, the delivered certificates and today's Python generators.
- [Consolidated V10 working draft](FORMAT_V10_DRAFT.md): strict improvement,
  complete-image exclusion, explicit affine input restrictions, and
  [joint bounded subflow](SUBFLOW_DRAFT.md).
  It is implemented under review and remains unfrozen.
- [V1 mathematical semantics and invariants](SEMANTICS_V1.md)
- [MCM/RPX V1 binary layout](FORMAT_V1.md)
- [RPA V1 text syntax](RPA_V1.md)
- [Trusted MPS dialect](MPS_V1.md)
- [Trusted LP dialect](LP_V1.md)
- [Trusted boundary and executed evidence](../audit/TRUST_REPORT.md)
- Rule arguments: [Flow](FLOW_V4.md), [Interval](INTERVAL_V5.md),
  [Menu and bijection](MENU_V7.md), [Signed](FORMAT_V8.md),
  [point contracts](POINT_V3.md), [complete fibers](FIBER_POINT_V6.md).

The documents below are the original **unimplemented D0 design draft**. They are
retained as design provenance and do not define the implemented V1 byte format.

# RPA/RPX 规范手册

这份中文 LaTeX 手册整理当前 RPA/RPX v0.1 设计，状态为 **D0 草案，尚未冻结**。
它是用于先讨论规范、再实现代码的工作文档；其中的工具命令与 VM 行为不是当前仓库已实现的功能声明。

- 主文件：[rpx-manual.tex](rpx-manual.tex)
- 阅读版：[rpx-manual.pdf](rpx-manual.pdf)
- 章节源文件：[rpx/chapters/](rpx/chapters/)

## 构建

需要 XeLaTeX、`ctex`、Fandol 字体和 `latexmk`。使用 TeX Live 的发行版本即可。

```bash
make -C docs
```

PDF 输出为 `docs/rpx-manual.pdf`；中间产物位于 `docs/.build/`。
手册使用 TeX Live 随附字体，不依赖某个用户安装的中文字体，也不需要 shell escape。

## 内容与审阅

手册覆盖模型和 contract、fact/scope/mapping 状态、全部 28 个 core opcode、RPA 语法、RPX 字节布局、loader、异常、完整证明示例和性能测量方法。

附录的 P-01 至 P-07 标记本次整理提出的具体修订；O-01 至 O-05 标记仍待决定的边界。
建议先审阅 contract 和分支汇合，再确认指令与二进制编码，最后冻结版本。
任何规范修改都应同步更新相关章节、完整示例和附录修订记录，再重新构建 PDF。

Implemented V8: [simultaneous activated signed decomposition](FORMAT_V8.md).
