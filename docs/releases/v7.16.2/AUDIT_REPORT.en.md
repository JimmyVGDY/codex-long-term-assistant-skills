<!-- Generated from locales/en/docs/releases/v7.16.2/AUDIT_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.16.2 Audit Report

Audit scope covers supplemental authorization, root accounting, concurrency, material refresh, compatibility and installation. Concrete independent-review conclusions must bind to the candidate's code fingerprint, packet and native result. This document does not create a passing status.

## Required invariants

1. Caller labels or hashes alone cannot authorize. A response must match the root, native source and concrete request.
2. Choose and spend one allocation under the root lock. Duplicate requests, concurrency and interruption recovery cannot duplicate grants or charges.
3. Roles, work and unapproved profiles cannot borrow allocations. Material refresh cannot reset stable work identity.
4. Running and unknown calls retain their handle. Created calls still settle after revocation or closure.
5. Preserve old prefixes and policy bytes, deploy compatible readers first, and never remove extension events during rollback.
6. Report local files, actual host execution, review results, commits, pushes and public publication separately.

## Permission and review limits

Reviewers are logical-readonly by default, not system-read-only without isolation evidence. Existing gates remain active; allowance grants do not bypass platform Hook trust or account limits. Unproven runtime states remain unverified. Consolidate confirmed findings before repair and targeted re-review.
