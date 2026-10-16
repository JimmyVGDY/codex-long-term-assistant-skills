<!-- Generated from locales/en/docs/SKILL_ARTIFACT_EVAL.md; edit that source and run scripts/documentation.py sync. -->

# Skill artifact comparison

scripts/skill-eval.py prepares public synthetic fixtures in the Plugin source repository, records actual artifacts and creates an offline comparison viewer. It reuses existing reuse cases, hidden assertions and UX metric contracts. It does not invoke models or treat self-reported completion or file existence as business success.

## Preparation and execution

Freeze cases, allowed changes, protected files, assertions, requested parameters and permission boundaries first. Pin baseline rules to a commit; candidate rules default to the working tree. Outputs require new external directories.

~~~text
python scripts/skill-eval.py prepare --suite <suite.json> --case <case-id> --baseline v7.16.2 --environment <environment.json> --output <new-external-directory>
python scripts/skill-eval.py prepare-reuse --case <existing-case-id> --baseline v7.16.2 --environment <environment.json> --allow-change <relative-file> --output <another-new-directory>
~~~

The suite schema is skill-eval-suite/1 with public-synthetic data. Each case declares task, skills, files, allowed_changes, artifacts and checks. Preparation rejects rule overrides, path escapes, links and sensitive material. The environment fixes platform, runtime, requested_model, requested_effort, permissions_digest and cache_condition. A permission digest records an authorized boundary; it grants no system permission.

Preparation produces independent directories, input manifests, rule snapshots and executor prompts. Executors read only their assigned rules and task material, without inspecting the other variant, input manifests or hidden answers. Keep requested parameters, environment and initial files equal. Use the same logical task budget without resetting charges through a new chat. Recover authorized external writes through the [artifact directory workflow](operations/artifact-scope.en.md).

## Capture, comparison and viewing

~~~text
python scripts/skill-eval.py verify-reuse --run <prepared-run-directory>
python scripts/skill-eval.py capture --input <run/input.json> --artifacts <run/workspace> --output <new-run-record.json>
python scripts/skill-eval.py compare --baseline <baseline-record.json> --candidate <candidate-record.json> --output <new-comparison.json>
python scripts/skill-eval.py render --comparison <comparison.json> --output <new-viewer.html>
~~~

Capture verifies protected files and actual outputs, preserving missing artifacts, empty files, failed assertions and unapproved changes. verify-reuse uses the original hidden oracle and records actual results separately; earlier failures remain. Comparison rechecks records, source files and conditions. Recomputing an outer digest cannot hide forged results. Different fixtures, environments, allowed changes or assertions are incomparable.

The viewer escapes all text; HTML artifacts are shown as source only. Bounded static PNGs can be embedded. It does not fetch remote images or execute scripts or artifacts. Each PNG is limited to 1 MiB, an 8192-pixel side and 8 Mi pixels. The full page limits preview input bytes to 4 MiB and images to 16 Mi pixels. Unsupported or oversized images retain their artifact records with an explicit preview limitation.

## Repeatable public synthetic cases

scripts/quality-fixtures.py --output <external-suite.json> builds twelve cases: three complete/incomplete document pairs, three frontend tasks and six MCP tool tasks. Use skill-eval.py prepare --suite <external-suite.json> --case <case-id> --baseline v7.16.2 --environment <environment.json> --output <external-run> to freeze rules and inputs. Reader and tool answer keys stay in evaluator input, outside executor context. Preserve actual native answers before evaluation; coordinators must not substitute correct answers.

Render frontend cases at 360x800 and 1280x900. Check task completion, content hierarchy, design-system consistency, legibility, focus, overflow, applicable states and reduced motion. Mechanical assertions cannot replace rendering. Repeat the recovery-document and local-design-extension cases three times per version, and repeat MCP pagination and permission cases three times as planned.

The MCP fixture implements a bounded local JSON-RPC subset pinned to the [2025-11-25 Tools contract](https://modelcontextprotocol.io/specification/2025-11-25/server/tools). It uses no live service and does not establish full protocol compliance or native Desktop MCP connector acceptance. A synthetic writer role is available only to unit-test construction; the executable fixture has a fixed reader identity. Preserve actual tool outputs separately from answer keys.

## Human feedback and evidence levels

~~~text
python scripts/skill-eval.py feedback-template --comparison <comparison.json> --output <new-feedback.json>
python scripts/skill-eval.py record-feedback --comparison <comparison.json> --feedback <filled-feedback.json> --output <new-feedback-record.json>
python scripts/skill-eval.py render --comparison <comparison.json> --feedback <feedback-record.json> --output <new-reviewed-viewer.html>
~~~

Feedback must reference actual artifacts and may record ties, insufficient evidence or inapplicability. Validation does not attest reviewer identity or blind isolation. Missing metrics remain UNKNOWN. Report mechanical checks, independent behavior and benefit separately. Without reliable independent samples, do not claim statistical improvement or automatically change Skills, routing policy or production code.

Synthetic host reports in tests and coordinator-authored demonstrations establish contracts or viewer behavior only, not independent model comparisons. Preserve earlier failures, missing audit callbacks and unexecuted host checks at their respective evidence levels.

Validation entrypoints: [tool regressions](../tests/test_skill_eval.py), [rule snapshots and separate directories](../tests/test_skill_fixture.py), [feedback and reuse assertions](../tests/test_skill_review.py).
