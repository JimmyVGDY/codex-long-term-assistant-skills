# Proposal Lifecycle V6

Recommended states:

`PENDING_REVIEW -> ACCEPTED/REJECTED/DEFERRED -> IMPLEMENTATION_LINKED -> VALIDATION_RECORDED -> CLOSED`

`SUPERSEDED` may close a Proposal replaced by newer evidence.

Hard boundaries:

- `execution_authorization=NONE` is permanent.
- After ACCEPT, create a separate implementation Task and obtain the authorization required by that Task.
- Implementation must bind a Git baseline; validation must bind the Commit or working-tree state and Evidence.
- A REJECTED Proposal must not be mechanically regenerated when its evidence summary, policy version, and observation window have not changed materially.
