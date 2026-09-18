# Multi-Agent Review Plan

## Basic Information

- Task ID:
- Feature boundary:
- Review phase: pre / post
- Risk level: Low / Medium / High / Critical
- Baseline Commit:
- Current HEAD:
- Diff scope:
- Minimum targeted validation:

## Runtime Isolation

- Reviewer TOML declaration:
- Actual parent-session sandbox:
- Confirmed use of the specified Agent:
- Probe result: not-run / sandbox-denied / permission-denied / write-succeeded / invalid
- Isolation level: system-readonly / logical-readonly / self-review / unknown
- Strict read-only review selected:
- Eligible for strict read-only review:
- Isolation evidence file:

## Budget

- Default maximum depth: 2
- Current depth: 0
- Maximum pre-implementation rounds: 1
- Default maximum post-implementation rounds: 2
- Current round: 1
- Default pre-implementation Reviewer ceiling: 2
- Default maximum parallel Reviewers: 3
- Default total Reviewer ceiling: 6
- Used / remaining: 0 / 6
- Default maximum centralized repair rounds: 2
- Default Terra High Reviewer ceiling: 1

## Reviewers in This Round

| Reviewer | Responsibility | Scope | Non-Responsibilities | Model Tier | Status |
|---|---|---|---|---|---|
|  |  |  |  | computed approved_profile (ten registered combinations) | Pending |

## Waiting and Consolidation Rules

- [ ] Wait for all applicable Reviewers before modifying code
- [ ] Reviewers are behaviorally read-only and may not modify or commit; when isolation is logical-readonly, explicitly state that it is not a system-isolation guarantee
- [ ] The coordinating Agent deduplicates, clusters root causes, and assigns severity
- [ ] Perform centralized repair only after defining the minimum complete repair set
- [ ] Check packet freshness and prevent unjustified repeat dispatch of the same Reviewer against the same packet

## Stop Conditions

-

## Selection evidence

- Policy ID/digest and scoring formula: reviewer-matrix-v2 / luna-evidence-v1
- Luna base 1 + review budget mode points + valid evidence awards:
- Excluded evidence and reasons; exact acceptable_profiles:
- Final profile; root permit and remaining budget:
- Sol/Astra <=2 attempts, <=1 concurrent; Astra High <=1; retries count.
