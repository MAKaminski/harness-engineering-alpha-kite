---
tracker:
  kind: linear
  url: https://linear.app/modularequity2   # Linear workspace (for links; API uses endpoint)
  endpoint: https://api.linear.app/graphql
  api_key: $LINEAR_API_KEY
  project_id: $LINEAR_PROJECT_ID   # optional: project UUID (preferred; avoids slugId 400)
  project_slug: $LINEAR_PROJECT_SLUG   # or set project slugId from project URL
  active_states: [Todo, "In Progress"]
  terminal_states: [Closed, Cancelled, Canceled, Duplicate, Done]

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
  # Local in-repo Codex-compatible app-server (no external codex binary required)
  # Use absolute path so it works from per-issue workspaces
  command: python3 /Users/makaminski1337/Developer/harness-engineering-alpha-kite/symphony/local_codex_server.py
  # approval_policy: never = auto-approve (Codex: untrusted | on-failure | on-request | reject | never)
  # thread_sandbox: workspace-write (Codex thread/start: read-only | workspace-write | danger-full-access)
  # turn_sandbox_policy: workspaceWrite (Codex turn sandboxPolicy.type: camelCase workspaceWrite | readOnly | dangerFullAccess | externalSandbox)
  turn_timeout_ms: 3600000
  read_timeout_ms: 120000   # 2 min for init/thread/turn handshakes (was 5s; avoids response_timeout)
  stall_timeout_ms: 600000   # 10 min before orchestrator marks session stalled
---

You are working on a Linear issue assigned to this session.

**Issue:** {{ issue.identifier }} – {{ issue.title }}

**Description:**
{{ issue.description }}

**State:** {{ issue.state }}
**Labels:** {{ issue.labels | join(", ") }}

{% if attempt %}
This is attempt {{ attempt }} (retry or continuation).
{% endif %}

Complete the work for this issue: implement the requested changes, run tests, and update the ticket or open a PR as appropriate. If you need to change issue state or add comments, use the available tracker tools.
