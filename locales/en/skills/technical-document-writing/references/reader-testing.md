# Reader testing

## When to use it

Use after substantial installation, deployment, recovery, cross-team architecture, or decision documents stabilize, or when asked whether another person can follow a document. Punctuation, terminology fixes, changelogs, and simple explanations retain the ordinary quality checklist without automatically adding readers. Infer audience and purpose from available material; clarify only consequential gaps.

## Freeze the inputs

Record the document version or digest and the reader's intended task. Adapt the following five concerns for operational documents; architecture documents may replace execution questions with decision rationale and alternatives.

| Concern | What the reader must establish |
|---|---|
| Applicability | Supported version, environment, role, and exclusions |
| Prerequisites | Inputs, permissions, configuration, and dependencies |
| Steps | First action, expected output, and conditions for continuing |
| Recovery | Where to stop, what to restore, and when to escalate |
| Completion | Evidence of success and remaining unverified items |

The author or maintainer fixes factual criteria before the reader run, outside reader-visible inputs. Do not change criteria to fit answers. Use the [reader test record](../assets/templates/reader-test.md) when useful; simple documents need not instantiate the full template.

## Independent reading

Within authorization and the existing budget, give a reader with no author conversation only the document, audience, and questions. Request answers, supporting passages, ambiguity, and missing prerequisites. Unavailable information is unanswerable. Do not supply answer keys, earlier reviews, conversation history, or suggested fixes.

This tests the document's sufficiency. The reader must not search source code, browse, or invent missing operations to repair it. Maintainers verify facts, commands, and interfaces separately against source or authoritative documentation. Comprehension does not establish factual correctness.

If no independent reader is available, retain author self-checks and unverified items; do not relabel same-context questioning as independence. Independent context also does not prove system-enforced read-only isolation.

## Revision and completion

Collect a round's findings, distinguish omissions, misinterpretations, factual errors, and out-of-scope requests, then revise together and retest affected questions. Preserve failed versions and digests. Do not repeat unchanged inputs without new information. Report specific remaining work when the budget or missing inputs prevents completion.

Reader comprehension may pass when critical questions have correct document-grounded answers and known blocking gaps are closed. Report factual verification, real operational validation, and uncovered audiences separately; this does not establish deployment success.

“Confirm things work after updating” lacks an executable standard. Use actual project material to provide version, prerequisites, checks, expected results, and recovery rather than inventing a convincing command.
