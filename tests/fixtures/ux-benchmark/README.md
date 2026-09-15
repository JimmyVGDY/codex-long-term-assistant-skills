# UX benchmark fixtures

These small public repositories are intentionally incomplete measurement inputs, not production code.
The collector does not execute these tasks automatically. The acceptance harness copies each scenario
into a fresh repository, records its initial bytes, and uses the same task and execution profile for
both package versions. A separate oracle checks the final code and allowed change scope.

- `simple-local-fix`: make `total([])` return zero while preserving integer summation; only `calculator.py` may change.
- `ordinary-feature-change`: normalize labels by trimming and collapsing whitespace and Unicode case folding;
  both catalog operations must use the same helper and duplicate normalized keys must still raise `ValueError`.
  Only `labels.py` and `catalog.py` may change.
- `cross-task-resume`: the harness records a valid checkpoint and evidence, then removes the negative-count
  guard. The subject only identifies stale validation and provides the next action; it must not repair code
  or update state during the query. The existing negative-count test remains failing by design.
  Context and evidence live outside the fixture repository, and their bytes must remain unchanged.

Model responses and business prompts are not fixture data. Observations contain only approved aggregate
fields; an agent saying PASS is not an oracle result. Small samples do not establish general speed gains.
