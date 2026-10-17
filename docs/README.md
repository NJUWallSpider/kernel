# RPX documentation

RPX 11 certifies only optimization equivalence of two complete MILPs. Every certificate contains one forward and one reverse proof tree. The kernel fixes integer feasibility and nonincreasing objectives; there are no property modes or independent Contracts.

- [Mathematical semantics](SEMANTICS.md) and [binary/JSON format](FORMAT.md).
- [Rust/CLI API](API.md), [Python authoring](COMPILER_API.md), and [author protocol](COMPILER_AGENT_PROTOCOL.md).
- [RPA 12 assembly](RPA.md) and [complete examples](rpx/examples/). The old `RPA 11` JSON and `RPA-S 1` text formats are rejected.
- Exact [MPS](MPS_V1.md) and [LP](LP_V1.md) import.
- Constructive [Flow](FLOW_V4.md), [Interval](INTERVAL_V5.md), [Menu](MENU_V7.md), and [Subflow](SUBFLOW_V10.md) arguments; [all five current lift semantics](SEMANTICS.md#joint-construction-rules).
- [Chinese PDF manual](rpx/rpx-manual.pdf) and [LaTeX source](rpx/rpx-manual.tex).

```sh
cargo build -p kernel-core --release --locked
cargo test -p kernel-core --locked
python3 tools/check_rpx_manual.py
python3 tools/check_docs.py
make -C docs/rpx pdf
```

The manual uses XeLaTeX, ctex, Fandol fonts and latexmk. Intermediate files stay under `docs/rpx/.build/`.

Historical compiler/agent/performance documents and case receipts preserve their original version and scope. They are not current API specifications. Old property-based certificates require the explicit [migration tool](../tools/migrate_mi_opt.py) with a separately supplied old decoder; RPX 11 does not retain a compatibility path.
