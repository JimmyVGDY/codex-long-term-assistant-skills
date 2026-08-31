# Existing-Document Changes, Memory Isolation, Quality Review, and Delivery

## Contents

- 9. Rules for Modifying Existing Documents
- 10. Separation of Formal Documentation and External Agent Memory
- 11. Documentation Quality Review
- 12. Final Delivery

## 9. Rules for Modifying Existing Documents

When modifying an existing document:

1. Read the complete document and relevant context.
2. Define the intended scope.
3. Preserve existing headings, numbering, links, terminology, and untouched content.
4. Do not rewrite unrelated sections opportunistically.
5. Check the table of contents, anchors, cross-references, and version information.
6. Record historical errors outside scope as items needing confirmation or additional findings.
7. After editing, check that definitions, numbers, states, and conclusions remain consistent.
8. Follow current authorization for overwriting, Git operations, or publication.

If the task explicitly calls for a comprehensive restructuring, the organization may change, but valid facts, business definitions, and traceability must be preserved.

---

## 10. Separation of Formal Documentation and External Agent Memory

Formal engineering documentation may enter the repository for team use, including:

- architecture documents;
- API documents;
- deployment runbooks;
- database designs;
- technical solutions;
- project README files;
- formal CHANGELOG files.

External agent memory exists only for task recovery, for example:

- `CURRENT_TASK.md`;
- `PLAN.md`;
- `PROGRESS.md`;
- `HANDOFF.md`;
- `DELIVERY_RECORD.md`.

Unless the project explicitly adopts these files as formal specifications, external memory must not enter the project repository, Git history, or formal CHANGELOG.

---

## 11. Documentation Quality Review

Before delivery, check at least the following dimensions.

### 11.1 Accuracy

- Do facts have sources?
- Are terms, versions, APIs, fields, and states accurate?
- Are inferences or plans presented falsely as facts?
- Are numbers and conclusions internally consistent?

### 11.2 Completeness

- Does the document cover what the intended reader needs?
- Are exceptions, compatibility, authorization, rollback, and validation covered?
- Are dependencies and unverified items explicit?

### 11.3 Consistency

- Are headings, numbering, names, states, and times consistent?
- Do diagrams, tables, and prose agree?
- Does the document agree with code, configuration, tests, and CHANGELOG?

### 11.4 Actionability

- Do implementation steps define prerequisites, inputs, outputs, and validation?
- Do operational commands state environment, permissions, and risks?
- Are stopping conditions and rollback defined?

### 11.5 Maintainability

- Are version, date, and applicability recorded?
- Does the document avoid copying large amounts of quickly stale source code?
- Can it be updated and searched easily?
- Does it avoid unnecessary repetition?

### 11.6 Security

- Does it contain passwords, tokens, keys, cookies, private data, or confidential organizational information?
- Does it provide unauthorized production write operations?
- Does it expose internal addresses, accounts, or real data?
- Are examples redacted?

### 11.7 Readability

- Does the summary communicate the conclusion quickly?
- Does each section address one clear topic?
- Do tables, lists, and diagrams materially improve comprehension?
- Does the technical depth fit the intended reader?

---

## 12. Final Delivery

According to task complexity, report:

- document name and purpose;
- primary evidence;
- created or modified files;
- key conclusions;
- confirmed facts, assumptions, and unverified items;
- whether the work was written to the repository, committed, pushed, or published;
- matters that still require requester confirmation.

A simple document does not need a mechanical full delivery report, but missing sources, unverified claims, or files that were not actually generated must never be concealed.
