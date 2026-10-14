# Original specification bytes

The active authority is [docs/FORMAT.md](../../docs/FORMAT.md). V9/V10 were frozen
on 2026-10-14; [the freeze record](../PROTOCOL_V9_V10_FREEZE.md) records the decision
and fresh validation. This directory contains historical evidence, not active
protocol references.

Three documents are named and hash-pinned by the original
[final_delivery_manifest.json](../final_delivery_manifest.json). They were copied
byte for byte before consolidation. The manifest remains unchanged: its paths
identify the original delivery snapshot, while these paths locate the preserved
bytes in today's tree.

| Original path | Preserved copy | Original SHA-256 |
|---|---|---|
| docs/CURRENT_FORMAT.md | [CURRENT_FORMAT.md](pre-freeze-2026-10-14/CURRENT_FORMAT.md) | b98fd7b3231984ab1ddc903f89c799879aac5fd88f2fe29da7e8af1acf3fa750 |
| docs/FORMAT_V10_DRAFT.md | [FORMAT_V10_DRAFT.md](pre-freeze-2026-10-14/FORMAT_V10_DRAFT.md) | 07f42567a0fb3e0d96d397b5e4d4da43aef0324542c558cf67e2971bf692c690 |
| docs/SUBFLOW_DRAFT.md | [SUBFLOW_DRAFT.md](pre-freeze-2026-10-14/SUBFLOW_DRAFT.md) | 0a33e61f186a1c14eb3c2c7084f8cccd88cb1f1c671e61dbbb6a70c477e90b66 |

Internal relative links in these original files intentionally retain their old
snapshot spelling. All ten FORMAT increments and their linked documents can be
retrieved with `git show 1468f95:docs/<original-name>`. Their former draft labels
and dated counts are historical facts and have not been rewritten as frozen
receipts. The current constructive subflow argument is [SUBFLOW_V10.md](../../docs/SUBFLOW_V10.md).
