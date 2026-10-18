Start with a self-contained variable elimination proof; no model files are required.

## Installation
Install the wheel with `python -m pip install /path/to/rpx.whl`. For a source checkout, run `cd python && maturin build --release`, then install the produced wheel. The Python module help is independent of the Kernel `rpx` executable.

## Run the first proof
Run `python -m rpx._help.examples.quickstart`. It builds source and target models, proves both directions, publishes in a temporary directory, runs the Kernel and requires VERIFIED. Read the installed source with:

```python
from importlib.resources import files
print(files("rpx._help.examples").joinpath("quickstart.py").read_text())
```

## What the proof does
The source has x0+x1=1, both variables in [0,1], minimizing x0. The target has y in [0,1], minimizing 1-y. Forward maps y to x1 and proves objective.non_increasing by negating the balance equality. Reverse maps x0 to 1-y and x1 to y. Both scopes finish, then verification checks MI_OPT. Successful finish or compilation alone is not certification.

## Next commands
`python -m rpx help workflow`
`python -m rpx help Scope.map`
`python -m rpx help agent`
