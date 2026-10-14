You are analyzing one mixed-integer linear optimization model directly from its MPS representation.

The model is available at `input/model.mps`. Use the persistent Python environment as your computational workspace. Keep parsed data, hypotheses, exact witnesses, and verification results alive across calls.

Your objective is to find the strongest meaningful, mathematically justified opportunity for exact simplification, reformulation, decomposition, redundancy removal, strengthening, or another useful structural improvement. Explore autonomously; do not assume that an improvement exists. Do not infer application semantics solely from names. Inspect the complete relevant scope for every substantive claim. Use exact arithmetic where coefficient exactness matters.

This is a solver-blind, single-commit evaluation. Do not use any optimization solver, presolver, LP relaxation, feasibility solver, solver-derived information, or solver-performance feedback. Do not invoke optimization indirectly through general-purpose libraries. Do not access the Internet or files outside this evaluation workspace. You may use ordinary Python and general-purpose libraries for sparse computation, graphs, symbolic arithmetic, and custom analysis.

The generic `kernel_compiler` Python package and its RPX kernel are available inside this workspace. They are proof-authoring and verification tools. They do not search for reformulations or proofs. Import the package directly in Python; read `compiler/API.md` for the public API. You may also inspect the generic package implementation under `compiler/python/kernel_compiler/`. The package and kernel are configured already; do not discover other environments. In this arm you may use this package to parse/read models, construct your own target model, state your own maps, and express your own proof. All mathematical decisions and nontrivial proof witnesses must come from you.

`Model.load` uses the Kernel's exact standard-format reader. Establish that the interpreted sections, domains, bounds, senses, and objective are reliable for your analysis. `proof.verify(..., committed_model=...)` independently reads the final standard artifact through the Kernel and compares its exact semantics with the target being proved; inspect that result as your serialization audit. A second custom MPS parser is optional. You do not need to reproduce the package's parser or serializer merely to express a proof. Independently verify your intended edits and mathematical witnesses using the supplied exact model readback and the checks appropriate to those edits.

The reformulation objective has the same priority as in an ordinary analysis without a compiler. Preserve opportunities for ambitious, complex reformulations. First investigate the model and decide what mathematical transformation is useful; then express its correctness proof. If expressing a justified reformulation is difficult, use the general proof builders, exact combinations, integer rounding, cases, or explicit extension witnesses as appropriate. Do not retreat to a weaker target merely because its certificate is easier. If a compiler limitation prevents certification, preserve your strongest justified target and report the exact limitation and a reproducible failing API call.

Treat observations, hypotheses, and checked claims separately. Samples and apparent patterns may suggest hypotheses but do not establish claims over the full scope. Failed or inconclusive checks must remain visible. Kernel acceptance proves only the submitted request: explain whether your request establishes full feasible-set equivalence, correspondence under a projection, integer strengthening with reverse relaxation, optimal-value equivalence, or some other relation. Do not describe a one-direction or restricted-domain proof as full equivalence.

You may test and refine structural hypotheses and proofs repeatedly. You receive no solver-performance feedback before the final commitment. You have exactly one final reformulation commitment. If no meaningful modification is justified, say so. If committing, preserve the original and write a separate final standard solver-readable LP or MPS artifact under `output/`. Independently check that this artifact matches your intended edits. Write sufficient audit information to identify all changes.

For a committed reformulation, create your proof with the Python API and call the kernel yourself. Save the proof as RPX and its request as JSON under `output/`, together with the exact source/target canonical models used. No RPA intermediate is necessary. Save a final `output/delivery.json` using paths relative to this workspace:

```json
{
  "committed_model": "output/reformulated.mps",
  "relation": "Describe the precise relation and any domain restrictions",
  "pieces": [
    {
      "source": "output/source.mcm",
      "target": "output/target.mcm",
      "proof": "output/proof.rpx",
      "request": "output/request.json"
    }
  ]
}
```

Use one piece for a single certificate. Multiple pieces mean all requests must be checked and their conjunction must establish your stated relation. Save the actual kernel result in `output/verification.json` and your runnable proof-construction code in `output/proof.py` or an equivalent Python artifact. If certification fails, still write the intended final target and delivery paths that exist, record the failure, and explain the unsupported obligation; do not claim acceptance.

Before ending, write `output/report.md` and give a concise final answer covering structural findings, parsing reliability, hypotheses tested (including rejected or inconclusive ones), the final reformulation and exact scope, the mathematical evidence and kernel claim coverage, artifact audit, remaining uncertainty, final artifact paths, and any concrete compiler feedback. Keep tool observations bounded; summarize large structures and inspect targeted subsets.
