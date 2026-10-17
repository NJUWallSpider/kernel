# Current repository tools

Run these from the repository root. The Rust `rpx` CLI performs verification;
Python tools prepare certificates, orchestrate checks, and summarize evidence.

| Task | Entry point |
| --- | --- |
| Manual examples and rejection checks | `check_rpx_manual.py` |
| Refresh native case deliveries | `prepare_test<case>.py --out cases/<case>` |

The case preparers now build proofs through `python/kernel_compiler` and write
current RPA 12 / RPX 11 artifacts with `prepare_native.compile_case`; they no
longer write certificate JSON, legacy `RPA n` text, `request.json`, or spawn
`rpx`. Run each preparer serially; native compilation/verification is in-process.
`prepare_test<case>.py --out cases/<case>` refreshes a delivery. Helpers such
as `parse_mps`, exact expression arithmetic, `fact`/`box`, and `substitute`
remain shared Python analysis utilities; they are not a second proof core.
