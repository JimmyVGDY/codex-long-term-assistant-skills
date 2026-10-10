# V7.16.0 audit scope

The repair follows actual entrypoints across native writes, workflow stages, indexes, context, budget receipts, and continuations without temporarily disabling existing gates.

Design review required installer-owned coverage and separation of logical-readonly from system isolation. The current diff still requires postimplementation review and native Desktop acceptance before release; native calls and historical ledgers remain distinct.

Default or degraded continuation grants no commit, push, publication, or production authority. Observation stores minimal metadata, not raw prompts, patches, complete answers, or credentials.
