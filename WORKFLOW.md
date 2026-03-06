---
tracker:
  kind: linear
  url: https://linear.app/modularequity2
  endpoint: https://api.linear.app/graphql
  api_key: $LINEAR_API_KEY
  project_id: $LINEAR_PROJECT_ID
  project_slug: $LINEAR_PROJECT_SLUG
  active_states: [Todo, "In Progress", "In Review"]
  terminal_states: [Done, Cancelled, Canceled, Duplicate]

polling:
  interval_ms: 30000

workspace:
  root: $TMPDIR/symphony_workspaces

hooks:
  timeout_ms: 60000
  after_create: |
    # Populate workspace with repo so Codex can edit real code.
    if [ ! -d .git ]; then
      git clone --depth 1 https://github.com/MAKaminski/harness-engineering-alpha-kite.git .
    fi

agent:
  max_concurrent_agents: 2
  max_turns: 20
  max_retry_backoff_ms: 300000

codex:
  command: cd /Users/makaminski1337/Developer/harness-engineering-alpha-kite && PYTHONPATH=/Users/makaminski1337/Developer/harness-engineering-alpha-kite python3 -m symphony.local_codex_server
  turn_timeout_ms: 3600000
  read_timeout_ms: 120000
  stall_timeout_ms: 600000
---

You are working on a Linear issue assigned to this Symphony session.

**Issue:** {{ issue.identifier }} – {{ issue.title }}
**Issue ID (Linear):** {{ issue.id }}
**State:** {{ issue.state }}
**Labels:** {{ issue.labels | join(", ") }}

**Description:**
{{ issue.description }}

{% if attempt %}
Retry attempt: {{ attempt }}
{% endif %}

Execution rules:

1. Implement only what this issue asks for. Do not pull in unrelated backlog work.
2. Use Linear MCP to add a delivery comment that includes:
   - Scope completed
   - Verification commands + results
   - Artifacts (URLs/files)
   - Blockers (if any)
3. If issue scope is complete and verified, move it to `Done`.
4. If external credentials/access block final validation, move it to `In Review` and list exact blockers.
5. Never mark an issue `Done` when blockers remain unresolved.
