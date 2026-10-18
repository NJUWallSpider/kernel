# rpx examples

Run from the repository root after `python3 -m pip install -e ./python`:

```sh
make -C docs/rpx check-compiler-api
```

| Script | Operation |
| --- | --- |
| [elimination.py](elimination.py) | ModelBuilder, named goal, reverse reconstruction |
| [redundant.py](redundant.py) | Read models and prove a redundant row |
| [piecewise.py](piecewise.py) | Explicit continuous split and child maps |
| [interval_lift.py](interval_lift.py) | Typed interval result and generated coordinate |
| [load_models.py](load_models.py) | Model.read and sparse named maps |

The [tutorial notebook](tutorial.ipynb) walks through these concepts, then
illustrates Cases, native views and ownership errors. Each example constructs
both directions and invokes the real Kernel; none reads a historical proof.
Scripts use temporary bundles. Choose a persistent path in `proof.compile()`
to retain the self-contained delivery. Pass `target_artifact=...` to retain and
audit the exact external target file as well.

See [Compiler API](../../../COMPILER_API.md) for the lifecycle and typed specs.

## Offline help

Start with `python -m rpx help quickstart` or `python -m rpx help agent`.
The wheel contains self-contained examples: `python -m rpx._help.examples.quickstart`
and `python -m rpx._help.examples.lifts`. See [offline help](../../../RPX_HELP.md).
