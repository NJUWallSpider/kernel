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
- [Current delivery and trust boundaries](../audit/FINAL_DELIVERY_REPORT.md)
  and [historical trust reviews](../audit/TRUST_REPORT.md)
- Rule arguments: [Flow](FLOW_V4.md), [Interval](INTERVAL_V5.md),
  [Menu and bijection](MENU_V7.md), [Signed](FORMAT_V8.md),
  [point contracts](POINT_V3.md), [complete fibers](FIBER_POINT_V6.md).

# RPA/RPX Kernel 中文规范手册

手册已依据当前安全 Rust kernel 全面重写，不再是未实现的 D0/v0.1 草案。
MCM 仅支持版本 1；RPA/RPX V1–V8 已冻结，V9/V10 已实现但协议仍未冻结。
实现完成与协议冻结分别记录，手册不会把工作草案视作已发布协议。
`CURRENT_FORMAT.md` 的原字节由交付 manifest 固定，其中旧手册的 D0 状态说明
属于交付时点；本页和新版手册说明当前状态，冻结布局和历史验收记录保留。

- 主文件：[rpx-manual.tex](rpx-manual.tex)
- 阅读版：[rpx-manual.pdf](rpx-manual.pdf)
- 章节源文件：[rpx/chapters/](rpx/chapters/)
- 可运行示例：[rpx/examples/](rpx/examples/)

## 构建与示例复核

需要 XeLaTeX、`ctex`、Fandol 字体和 `latexmk`。使用 TeX Live 的发行版本即可。

```bash
make -C docs
```

PDF 输出为 `docs/rpx-manual.pdf`；中间产物位于 `docs/.build/`。
手册使用 TeX Live 随附字体，不依赖用户安装的中文字体，不需要 shell escape。
从仓库根目录复核三份完整示例：

```bash
cargo build -p kernel-core --release --locked
python3 tools/check_rpx_manual.py --kernel target/release/rpx
```

复核会从 LP 和 RPA 原文生成临时 MCM/RPX，验证独立 request、转换往返及负例。
汇编成功与数学验证成功分别检查；示例不使用摘要占位值或外部求解器。

## 内容与维护标准

手册保持完整中文规范参考的标准：数学模型与调用者 contract、fact/scope 状态、
全部推导与终结点的前置条件及拒绝条件、联合扩展引理、严格 JSON RPA、
逐字段 MCM/RPX 布局、可信 MPS/LP 导入、公开 API/CLI、资源预算与诊断、
完整双向示例、实际案例及性能证据。附录记录 V1–V10 能力历史、D0 决定的实现对应和可信边界。

任何规则或格式修改都须同步相关章节、完整示例和版本记录，再重新构建 PDF。
新增功能不能静默重解释已冻结字节；测试与语料验收不替代协议冻结或实现的形式化证明。
当前交付状态见 [完整交付报告](../audit/FINAL_DELIVERY_REPORT.md)，
历史 checkpoint 的测试和案例数量保留其原始含义。

## 已替代的设计文档

旧 `FIBER_STRICTNESS_DESIGN.md` 的未实现提案已由
[V6 格式](FORMAT_V6.md)和[完整 fiber 语义](FIBER_POINT_V6.md)取代。
旧 `FLOW_PRUNE_DESIGN.md` 提出的端点没有注册；当前实现使用
[V10 SubflowLift](SUBFLOW_DRAFT.md)，其终点限制和 tag 也不同。
这两份重复或过时提案已从当前文档目录删除，原文保留在 Git 提交 `bbeb994`。
历史 manifest 中的原路径和哈希不改写为当前规范。

当前工具入口及已移除实验脚本见[工具目录说明](../tools/README.md)。
