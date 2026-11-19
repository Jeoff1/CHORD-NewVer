---
status: accepted
---

# The final say on lineups is its own permission, worship.finalize_lineup

The pastor's decision on a lineup is final ([[Concept-Brief]]). That final
say is a dedicated permission, `worship.finalize_lineup`. The Pastoral
Staff role holds it by default, and the Administrator holds it as it holds
every permission. Code checks only this permission, never a role name, so
each church decides who has the final say
([[0001-configure-behavior-not-identity]], [[0003-editable-roles]]).
Decided on 2026-11-19 from the [[2026-11-19-Workflow-Review]] (findings
F1c and F6). The rules it gates are in [[Design-Decisions]], Phase 6.

## Considered Options

- **Checking the Pastoral Staff role by name.** This breaks the core rule.
  A church that renames the role, or splits it, would lose the final say
  without noticing. Rejected.
- **Reusing an existing permission**, such as `worship.change_theme`, or the
  `change_lineup` permission that Phase 6 adds. The worship leader needs
  `change_lineup` to edit lineups, and `change_theme` is about themes. Either
  would tie the final say to an unrelated right. Rejected.

## Consequences

- The permission gives:
  - the **pastor's lock**: confirming a lineup, or editing a confirmed
    one, locks out everyone without the permission;
  - reopening a lineup;
  - sending a lineup back;
  - the "Edited by <pastor Label> (<person's name>)" mark.
- A holder of the permission is never locked out. Two people who both hold
  it can each change a lineup the other confirmed.
- **Administrators have the final say too**, because the Administrator role
  always regains every permission. An Administrator's confirmation locks the
  worship leader out, and their edit to a confirmed lineup is marked
  "Edited by Pastor (<their name>)".
- The mark names the person and uses the church's `pastor` Label (default
  "Pastor"). It reads correctly however the church names its roles.
- Hard to reverse: once churches have granted `worship.finalize_lineup` to
  their roles, renaming or replacing it needs a data migration of those
  grants.
