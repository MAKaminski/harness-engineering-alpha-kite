# Symphony + Linear Issue Transition Protocol

## Status flow

`Todo -> In Progress -> In Review/Done`

- Move to `In Progress` when implementation begins.
- Move to `Done` only if scoped code, docs, and local checks pass and no external blocker remains.
- Move to `In Review` if work is complete locally but external validation (deployment/provider auth) is blocked.

## Mandatory end-of-issue comment template

```md
### Delivery Summary
- Scope completed:
- Key files touched:

### Verification
- Command:
- Result:

### Artifacts
- URLs / scripts / schema files:

### Blockers
- None | <explicit blocker + required credential/action>
```

## Symphony prompt guardrails

- Implement only what the current issue requests.
- Use Linear MCP for comments and state transitions.
- Do not mark an issue `Done` if blocked by missing external credentials.
