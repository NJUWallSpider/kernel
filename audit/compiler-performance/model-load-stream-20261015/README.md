This measures only `Model.load` on the pristine test16 input, using the fixed
release Kernel and three serial fresh processes per arm. It compares the
231e6f4 Python package with the pending bounded MCM stream reader. It runs no
solver, proof search or Agent. The old and new packages are copied to private
temporary directories before measuring; the report binds every Python source
and the native binary by SHA-256.

The native canonical MCM and exported JSON are prepared outside the timed
region and match the retained C7 input artifacts exactly. All six loaded
Python models reencode to the exact native MCM bytes. One process per arm also
compares every field against the independent native JSON export. These checks
and model statistics run after the load timer and its memory sample.

`load_parent_peak_rss_bytes` is Darwin `RUSAGE_SELF.ru_maxrss` sampled immediately
after loading: the Python parent's historical maximum RSS, in bytes. It excludes
native child processes and is not a process-tree peak. The separately recorded
whole-worker peak includes the later validation. No OS cache flush is performed;
native oracle preparation reads the input first. This is a load microbenchmark,
not an end-to-end Agent speed measurement.

Reproduce from the repository root with the same old package checkout (or an
equivalent `git archive 231e6f4 python/kernel_compiler` extraction):

```sh
/Users/bhz/miniforge3/envs/bigdata/bin/python audit/compiler-performance/model-load-stream-20261015/benchmark.py \
  --old-pythonpath /Users/bhz/Code/reform_test/runs/compiler-package-C7-231e6f4-20261015/python \
  --new-pythonpath /Users/bhz/Code/kernel/python \
  --binary /Users/bhz/Code/kernel/target/release/rpx \
  --input /Users/bhz/Code/reform_test/runs/test16-compiler-compiler-batch-C7-20261015/input/model.mps \
  --expected-input-sha256 d39273f74cdd8249ff459ae5c4056753ab11036d02624c09470b6949fbc071b4 \
  --retained-mcm /Users/bhz/Code/reform_test/runs/test16-compiler-compiler-batch-C7-20261015/harness-assessment/input.mcm \
  --retained-json /Users/bhz/Code/reform_test/runs/test16-compiler-compiler-batch-C7-20261015/harness-assessment/input.model.json \
  --report /tmp/model-load-comparison.json
```

`report.json` also records the four successful Python/tools suite commands,
versions, counts and runner times. Large inputs, native exports and model
snapshots remain outside Git and are not copied into this audit directory.
