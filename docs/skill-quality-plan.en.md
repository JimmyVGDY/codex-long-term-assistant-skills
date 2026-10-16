<!-- Generated from locales/en/docs/skill-quality-plan.md; edit that source and run scripts/documentation.py sync. -->

# Plugin Skill quality: six-track initiative and implementation plan

- Initiative: `SKILL-QUALITY-20261015`.
- Date: 2026-10-15, Asia/Shanghai.
- Status: all six tracks are authorized through commit, push and public release. Main tools, references and synthetic cases are implemented; real Desktop comparisons and publication remain pending.
- Implementation baseline: official v7.16.2 at `2604e8bea96294c696106935186ebeab1df9a0e4`, explicitly selected by the user; use this initiative's independent implementation branch.
- Repository: [codex-long-term-assistant-skills](https://github.com/JimmyVGDY/codex-long-term-assistant-skills).
- Product: Codex Desktop. Internal management and evaluation scripts do not create a standalone CLI product or acceptance track.
- Readers: implementers, maintainers, and independent reviewers.
- Completion: all six tracks require deliverables and acceptance evidence. Starting with the first three does not make the remaining three optional.

## 1. Objective, scope, and authorization

Make the existing Skills' workflows more concrete, verify actual outputs, and use repeatable comparisons to establish whether changes help. Reuse the existing project binding, budget, review, installation, and delivery mechanisms.

| ID | Required track | Verifiable result |
|---|---|---|
| W01 | Skill output comparison entry point | Compare baseline and candidate outputs, assertions, available cost metrics, and human judgments for the same task. |
| W02 | Documentation reader testing | Detect missing prerequisites, author-only context, ambiguity, and steps a reader cannot execute. |
| W03 | Frontend design workflow | Ground design in real content, user tasks, and the existing design system; inspect the rendered result. |
| W04 | Skill triggering evaluation | Cover informal language, adjacent negative cases, mixed intent, and phase changes; distinguish missed, wrong, and excessive activation. |
| W05 | Browser acceptance workflow | Make readiness, actions, assertions, screenshots, logs, and resource cleanup executable steps. |
| W06 | MCP tool design and acceptance | Supply concrete contracts and validate composed tasks, pagination, errors, and permission boundaries. |

After initiation, the user explicitly authorized executing this plan through commit, push, and public release, and selected 7.16.2 as the implementation baseline. Those direct instructions provide current authorization; the plan and Evidence do not independently grant permissions. Experiments, installation, deployment, and restarts follow actual task scope and existing gates without requesting already-granted permission again. Optimization proposals retain `execution_authorization=NONE`.

This is a manually requested initiative, not a claim that cross-task statistics generated an Evolution Proposal or proved benefits. No statistical evolution analysis, benefit registration, or routing-policy change has been performed.

### 1.1 Constraints

- Keep the existing ten Skills. Prefer conditional references, templates, examples, and maintenance tools.
- Preserve the governance runtime, budget ledger, approval contracts, review controller, and installation transactions.
- Do not automatically rewrite descriptions or accept experiment results. Do not collect complete business prompts, answers, code, logs, or credentials by default.
- Do not introduce an upstream-specific SDK or model CLI, a new model account, a persistent evaluation service, or a frontend build chain.
- Do not revive frozen statistical model-qualification gates. Use the current script-based decisions and shared budget.
- Do not import restricted document-generation assets or add Word, PDF, presentation, or spreadsheet generation.
- Deliver source and bilingual product documentation according to repository conventions. Keep task state, raw experiment outputs, and control records outside the source repository.

### 1.2 User-added gate improvements

This task also fixes external task artifacts incorrectly rejected as PATH_ESCAPE, chat-wide budget ownership, broad blocking from missing post-write receipts, and treating UNKNOWN as proof that work did not run or requires restart. Preserve identity, file permissions, provenance integrity and actual budget limits. Independent objectives receive task scopes; repairs, continuations, splits and subagents retain the original ledger. Review and execution allowances remain role-bound, and new formats require matching installed readers. See [task budgets](operations/task-budget-scope.en.md), [artifact scopes](operations/artifact-scope.en.md) and [gate recovery](operations/gate-recovery-policy.en.md).

## 2. Observed baseline and implementation preflight

| Item | Observation on 2026-10-15 | Implementation requirement |
|---|---|---|
| Git root | Target repository verified; the local absolute path remains only in the external Project Profile | Recheck root, remote, branch, and working state. |
| Remote | `https://github.com/JimmyVGDY/codex-long-term-assistant-skills.git` | An identity conflict stops the affected action. |
| Branch / HEAD | Review-allowance branch / `80124ae6d70fd445af66fd8c0c21c3b8dea53471` | This belongs to separate work; keep this initiative's implementation out of that branch. |
| Working tree | No output from `git status --porcelain=v1` | Preserve concurrent changes that appear later. |
| Package / Plugin manifests | `7.16.2` | This does not establish publication, installation, or active host behavior. |
| Separate PR | [#24: review allowance amendments and authorization recovery](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/pull/24), open when checked | Start implementation from a confirmed integration baseline; do not merge, repair, or publish that PR as part of initiation. |
| Stack | Standard-library Python tools, Markdown/JSON, bilingual distribution; minimum Python 3.11, declared CI 3.11/3.13 | No stack upgrade. The planning host's Python 3.14.7 was used for record tools, not as acceptance of the declared matrix. |
| Skills / routing | Ten Skills, 52 routing cases, 16 representative host-profile cases | Recalculate from current files instead of hardcoding these counts. |
| Target version, schedule, actual cost | Pending final change scope, resources, and version availability | Do not reserve a version or promise unmeasured dates and costs. |

Before implementation, verify repository identity against an external Project Profile. Historical machine-path mismatches invalidate reuse of its authorization and evidence. Planning, tool checks, installation, and host behavior are distinct evidence layers.

### 2.1 Existing assets to reuse

| Asset | Existing capability | Increment |
|---|---|---|
| `scripts/reuse-eval.py`, `tests/reuse-fixtures.json`, `tests/reuse-oracles.json` | Isolated fixtures, historical rules, protected inputs, hidden assertions, output digests | Add general orchestration and output viewing while preserving existing entry-point behavior. |
| `scripts/ux-benchmark.py`, `tests/test_ux_benchmark.py` | Whitelisted metrics, comparability checks, successful-run statistics, before/after comparison | Reference its results without inserting arbitrary artifact text into its old metric contract. |
| `scripts/routing-eval.py`, routing cases, host acceptance profile | Required/optional/forbidden sets, phase and count limits, host final-report verification | Add sample partitions, repeated observations, categorized results, and candidate assessment. |
| `skills/technical-document-writing/` | Audience, facts, templates, quality checks | Conditional reader testing. |
| `skills/frontend-engineering/` | Frameworks, design systems, browser boundaries, performance, accessibility, validation matrix | Design and browser execution workflows. |
| `skills/ai-engineering/references/agent-tool-workflows.md` | Schemas, permissions, idempotency, timeouts, budget, state | MCP-specific examples and task acceptance. |

The three evaluation scripts, three domain Skill directories, and routing cases did not change between the preceding analysis baseline and this HEAD. This scoped comparison does not replace implementation-time checks.

## 3. Phases and dependencies

Use one initiative and six work packages. Each has a separately reviewable, verifiable and reversible boundary. Commit, push and public release use the authorization already granted for this task.

| Phase | Deliverable | Dependency | Exit evidence |
|---|---|---|---|
| S0 | Confirm integration baseline; freeze fixtures, metrics, paths, and experiment budget | Implementation authorization | Consistent identity and scope; conflicts restrict only affected actions. |
| S1 | W01 minimum evaluation entry point and offline viewer | S0 | Compatibility, malformed inputs, path and display boundaries pass; results can be read back. |
| S2 | W02 reader workflow and W03 design workflow | S1 evidence format | Entry points, positive/negative cases, and small-sample behavior results for both. |
| S3 | W04 routing evaluation | S1 and stable W02/W03 candidate entry points | Compatible contracts, independent final set, authentic observation sources. |
| S4 | W05 browser workflow and W06 MCP guidance | S1; W03 supplies page examples | Browser actions/cleanup and tool composition/permission cases pass. |
| S5 | Six-track integration, bilingual coverage, regression checks, independent review | All six candidates | Consolidate findings before repairs; refresh affected evidence. |
| S6 | Artifacts, installation, and fresh Desktop-task acceptance | S5 and relevant operation authorization | Separate readback of source, artifacts, installation, and actual loading. |

Default order is S0 → S1 → S2 → S3 → S4 → S5 → S6. Independent documents or fixtures may be prepared concurrently; the coordinator owns shared entry points, contracts, and localization. Do not mechanically spawn six agents. Actual delegation follows applicable instructions, authorization, script-selected settings, and the shared budget.

## 4. Work packages

The work packages preserve design and acceptance requirements; current source is authoritative for implemented paths. Extend existing assets serving the same purpose and retain requirement and acceptance IDs.

### W01: Skill output comparison

**Objective.** Determine whether the candidate improves outputs, causes regressions, or only adds cost. Deliver verifiable comparisons before claiming a benefit.

**Implementation.** Proposed assets: `scripts/skill-eval.py`, `tests/test_skill_eval.py`, `tests/fixtures/skill-eval/`, and `docs/SKILL_ARTIFACT_EVAL.md`. Extract reusable pure functions where justified while preserving old commands and records. Use static local HTML; add no persistent service or build chain.

**Workflow.** Explicitly select task and baseline/candidate rules → prepare independent directories → execute in independent Desktop tasks → import evidence → mechanically check outputs and invariants → display comparison → record human judgment. The tool does not call models or perform remote writes by default.

**Record contract.** Include case/input digests, source commit/rule digests, requested model/effort, tool permissions, environment, sample ID, relative artifact paths/digests, check results and evidence locations, timing, and sourced counts. Unknown usage stays UNKNOWN. Requested model identity is not proof of the host's actual backend model. Deliberately authored public synthetic prompts may be stored; business transcripts are not default inputs.

**Isolation.** Keep artifacts and human feedback outside the repository. A separate evaluation manifest references existing UX results instead of broadening its whitelist. Baseline and candidate retain the same permissions, budgets, and mandatory controls. Oracles and blinded version mappings are evaluator-only. Directory/instruction separation is logical isolation unless stronger enforcement is proven.

**W01-A.** Cover valid/missing/corrupt reports, incomparable inputs, duplicate samples, path traversal, links/reparse points, protected-file changes, empty outputs, and malicious HTML. Bound file counts and sizes. Escape untrusted text; do not execute artifact code or load remote resources by default. Interactive previews require separately established isolation. Recalculation is deterministic; failed evidence is preserved.

**W01-B.** Run an existing reuse fixture once with each version end to end. Inspect actual outputs and independent assertions. Assess whether assertions can distinguish wrong content; file existence is insufficient. Optional blind comparison permits ties and insufficient evidence.

**Rollback.** Remove this package's entry point/assets while existing reuse and UX tools remain usable. Preserve readable experiment and failure records.

### W02: Documentation reader testing

**Objective.** A reader can understand critical prerequisites and actions without the author's conversation.

**Implementation.** Add proposed `references/reader-testing.md`, `assets/templates/reader-test.md`, and examples under `skills/technical-document-writing/`. Link conditionally from the Skill and `document-maintenance-quality.md`.

**Trigger.** Installation, deployment, recovery, cross-team architecture/decision documents, or explicit requests to validate usability. Punctuation, narrow terminology edits, changelogs, and simple explanations do not automatically start independent readers.

**Workflow.** Freeze document/audience → predefine five critical questions and criteria → give a fresh reader only the document/questions → collect answers, source paragraphs, and gaps → revise together → rerun affected questions. Do not reveal answer keys. Verify facts separately against code or authoritative sources.

**W02-A.** Use installation, recovery, and architecture-decision documents, each with complete and deliberately incomplete variants. Correct variants support all critical answers; incomplete variants expose missing prerequisites without invented commands or permission assumptions.

**W02-B.** Compare old/new rules once per category; repeat the critical recovery case three times per version for consistency screening. Without an independent reader, report insufficient evidence rather than relabeling author self-review.

**Rollback.** Remove added pointers/assets while preserving existing quality dimensions and templates.

### W03: Frontend design workflow

**Objective.** Design choices serve actual content, audience, and primary tasks and survive inspection of rendered output.

**Implementation.** Add proposed `references/design-workflow.md`, a concise design brief template, and examples under `skills/frontend-engineering/`. Reuse design-system, quality, and accessibility rules.

**Workflow.** Identify users/tasks/content → inspect existing components and design system → outline palette, typography, layout, interaction, and motion → check against requirements → implement → inspect screenshots at target sizes → repair concrete problems. Existing products retain their established system; user direction takes precedence over generic aesthetic preferences.

**W03-A.** Cover a new public page, an existing administrative form, and a local design-system extension. Capture desktop/mobile rendering and applicable focus, legibility, overflow, loading/empty/error states, and reduced-motion behavior.

**W03-B.** Predefine content hierarchy, task completion, consistency, and legibility criteria. Compare each category once; repeat the local-extension case three times per version. Detect unnecessary theme replacement, component substitution, or dependency upgrades. Screenshots, color counts, and self-declared beauty are not acceptance criteria.

**Rollback.** Remove the added design workflow and references while preserving framework, security, and compatibility guidance.

### W04: Skill triggering evaluation

**Objective.** Improve distinction between realistic requests and adjacent tasks without unnecessary loading; verify improvement through observations.

**Implementation.** Extend existing routing tools, cases, host guidance, and tests. Preserve existing schemas and required/optional/forbidden/max_active/phases semantics. Use explicit versioning for incompatible contracts rather than reinterpreting history.

**Samples.** Start with 24 manually authored candidates: 12 positives and 12 near-miss negatives across documentation, frontend design, browser validation, and MCP, six per group. Include informal language, mixed intent, and phase changes. Partition by intent family into 16 development and eight final cases. Related paraphrases cannot cross partitions; both partitions cover all four groups and both classes. Do not repeatedly select descriptions on the final set.

**Execution.** Fix requested model/effort, installed version, inputs, and permissions. Repeat critical ambiguous cases independently three times. Report misses, forbidden activations, excessive loading, and phase errors separately. Self-reported final output remains host_final_report evidence; only observed reads/calls establish a trace. Do not fill missing observations from expectations.

**W04-A.** Preserve scoring and structure of the original 52 cases and host profile; prevent contradictory required/forbidden sets. Safety and authorization negatives must not violate boundaries. Record other failures without relaxing criteria or enlarging optional sets to erase them.

**W04-B.** Adopt description changes only when final acceptance and quality floors support them. If improvement is unproven, retain the evaluation capability and old description. Replace a final set that leaked or influenced tuning; preserve old results and limitations.

**Rollback.** Restore descriptions/cases while preserving old parsing and records. Do not update model policies or historical ledgers automatically.

### W05: Browser acceptance workflow

**Objective.** Tie runtime conclusions to actual interactions, the correct environment, and recoverable resources.

**Implementation.** Add proposed `skills/frontend-engineering/references/browser-validation.md`, extend `FRONTEND_VALIDATION_MATRIX.template.md`, and provide a few synthetic cases. Add a small helper only for demonstrated repetition. Do not install browsers or take over user services by default.

**Workflow.** Identify existing services/test entry points → verify service identity/page readiness → locate controls from rendered DOM/screenshots → act and assert → capture sanitized screenshots/relevant errors → release owned resources. Distinguish builds, browser interactions, and real backend integration.

**W05-A.** Cover static pages, separate frontend/backend, failed requests/empty data, and repeated actions/races, including an already-running user service. An open port does not establish correct-service readiness. Use specific page/element assertions instead of treating network idle as a universal readiness condition.

**W05-B.** Reuse project tests and supported host browser interfaces, respecting tool-access rules. Helpers use argument arrays, bounded working directories/timeouts, and verified process ownership. Failure/cancellation releases only browsers, services, and child processes created for the run. Preserve user services. Verify Windows; report other platforms separately.

**Rollback.** Remove added workflow/helpers and restore project entry points. Never clean up globally by process name or port.

### W06: MCP tool design and acceptance

**Objective.** Agents can discover and compose tools from their contracts and provide reliable next steps on errors or denied access.

**Implementation.** Add proposed `references/mcp-tool-design.md`, a contract template, and a few positive/negative examples under `skills/ai-engineering/`, linked from `agent-tool-workflows.md`. Combine existing backend guidance for implementation mechanisms; add no separate MCP domain Skill.

**Contract.** Cover naming, constrained inputs, structured outputs, pagination/size bounds, timeouts, error categories and recovery guidance, authorization/tenancy, idempotency, and side effects. Annotations are hints, not substitutes for authorization or runtime permissions.

**W06-A.** Use fixed local synthetic data for six independent tasks: discover/select a tool, search across pages, compose two queries, handle empty/invalid inputs, handle denied access/tenant isolation, and handle timeouts/partial failures. Freeze correct answers; do not depend on changing online state.

**W06-B.** Observe tool selection, complete-result handling, and error explanations. Repeat permission and pagination cases three times for consistency screening. Validate write authorization, idempotency, and errors only in isolated fixtures; read-only success does not prove real write behavior. Create no external business records and request no production credentials.

**Rollback.** Remove the specialized references/examples while preserving core tool and bounded-loop rules.

## 5. Acceptance and benefit claims

### 5.1 Three separate decisions

1. Implementation: entry points, formats, boundaries, compatibility, errors, and cleanup meet their contracts.
2. Behavior: independent tasks complete cases with outputs and independent verification; executor claims alone are insufficient.
3. Benefit: comparable conditions show a meaningful quality/cost difference. Small samples support observations, not general reliability or statistical significance.

Use existing terminal outcomes PASS/BLOCKED/FAILED/CANCELLED/PARTIAL/UNKNOWN. Initiated and awaiting implementation are planning states, not runtime outcomes. Do not count ties, insufficient evidence, or inapplicable checks as successful runs.

### 5.2 Baselines, budgets, and experiments

- S0 freezes inputs, invariants, allowed edits, evaluator roles, and visible material. Exclude non-freezable cases from comparable results.
- Use independent tasks/directories with identical requested model/effort, permissions, environment, and initial files. Do not infer backend model identity.
- Count independent tasks/cases, not lifecycle events or correlated paraphrases.
- Changed rules or inputs invalidate affected checks/reviews. Preserve prior results and rerun affected cases.
- Do not invent 20% or 30% improvement targets. After baseline collection, preregister objectives and permitted regressions before freezing the candidate.
- Safety, permissions, data integrity, and protected inputs must all pass; speed or subjective scores cannot compensate.
- S0 computes total runs from cases, versions, repetitions, and required review reserves. Existing scripts/root ledgers govern spending. Execute in batches when necessary; do not reset cumulative usage or weaken acceptance.
- All six tracks enter the completion matrix. Report unproven benefits honestly and retain useful evaluation capabilities without manufacturing favorable judgments.

### 5.3 Targeted and integrated checks

After behavioral tool changes, run relevant existing reuse/UX tests, routing phase/host-acceptance tests, and new evaluation tests. Confirm exact commands from actual entry points; proposed filenames are not existing commands.

At S5, run existing `localization-audit.py --strict`, `check-links.py --strict`, `validate-package.py`, and affected documentation/distribution checks as appropriate to the final diff. Supply separate Chinese/English product documents and required code comments. Update affected manifests, payloads, and localization coverage. Use the declared runtime matrix.

Review W01 display/path/evidence changes for security, data contracts, and compatibility; W04 for routing compatibility and evidence; W05 for cancellation, ownership, and permissions. Use existing independent-review procedures according to risk, aggregate findings before repairs, and do not introduce a new reviewer model-routing system.

## 6. Risks and recovery

| Risk | Control or stopping condition | Recovery |
|---|---|---|
| Baseline or other PR changes | Keep implementation separate from #24; recheck each phase | Continue from confirmed current state; preserve others' changes. |
| Added process burden | Conditional loading; compare reads, calls, and confirmations | Remove mandatory steps with no demonstrated value; keep optional maintenance tools. |
| Leakage or overfitting | Hide oracles/opposite outputs; exclude final cases from tuning | Replace the independent final set; retain limitations of earlier runs. |
| Artifact injection or sensitive data | Untrusted rendering, bounded paths/sizes, no remote resources by default | Stop affected rendering/export, repair, rerun synthetic adversarial cases. |
| Leaked processes or incorrect cleanup | Release only proven run-owned resources; test cancellation | Recover precisely, never kill globally by name. |
| Unknown traces or costs | Preserve UNKNOWN and evidence level | Continue supported checks; strengthen claims only after obtaining evidence. |
| License or host differences | Pin upstream, design independently, check per-directory terms | Exclude restricted assets; use actual Desktop capabilities. |

Failures restrict only affected actions and dependencies. Never weaken gates to bypass unauthorized operations, identity conflicts, corrupt evidence, or real budget limits.

## 7. Ownership, versions, and delivery

- The coordinator owns scope, plan, identity, baseline, completion matrix, and shared edits.
- Implementers deliver within explicit file boundaries and preserve others' work.
- Evaluators verify artifacts and hidden criteria; they do not fill gaps with executor claims or own the total budget.
- Maintainers/users determine implementation resources, costs, and Git/installation/publication authorization. Named owners and dates remain to be assigned.

The implementation branch uses the user-agreed prefix and was created from the confirmed baseline. Check target-version availability before release. Clean temporary branches through recovery/worktree checks after merging. Report implementation, checks, review, commits, pushes, artifacts, installation, restarts and effective behavior separately.

## 8. Initiation status and next action

- [x] All six tracks are required; the first three run earlier without removing the others.
- [x] Existing assets, baseline, tests, and the separate active PR have been identified.
- [x] Each track has deliverables, dependencies, acceptance criteria, stopping conditions, and rollback.
- [ ] Implement tools, Skill guidance, and bilingual assets.
- [ ] Complete comparative experiments, behavior acceptance, and necessary independent review.
- [ ] Complete Git, installation, release, and fresh Desktop-task acceptance within actual authorization.

Implementation update: #24 merged, and this initiative's independent branch fast-forwarded to the official v7.16.2 tag while preserving the plans and W01 candidate. Tests from the previous 7.16.1 baseline are not delivery evidence; rerun on 7.16.2, then continue W01–W06 and later phases. Detailed execution evidence remains in external task records.

This is formal project planning documentation, not Agent external memory or runtime authorization. Keep subsequent control records and experiment artifacts in an available external directory under existing rules, not in this file or source repository.

## 9. Sources

Pin references to `anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44`. Reuse methods, not copied implementation/assets. Upstream host behavior does not prove Desktop compatibility.

- W01/W04: [Skill Creator](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator/SKILL.md), [Grader](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator/agents/grader.md).
- W02: [Doc Co-authoring](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/doc-coauthoring/SKILL.md).
- W03: [Frontend Design](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md).
- W05: [Webapp Testing](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/webapp-testing/SKILL.md).
- W06: [MCP Builder](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/mcp-builder/SKILL.md).
- [README licensing distinction](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/README.md): check the relevant directory and third-party notices before any concrete reuse.
