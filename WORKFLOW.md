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

agent:
  max_concurrent_agents: 2
  max_turns: 20
  max_retry_backoff_ms: 300000

codex:
  # Use full path if codex is not on PATH for bash -lc (e.g. /usr/local/bin/codex app-server or npx codex app-server)
  command: codex app-server
  # approval_policy: never = auto-approve (Codex: untrusted | on-failure | on-request | reject | never)
  # thread_sandbox / turn_sandbox_policy: workspace-write = allow edits (Codex: read-only | workspace-write | danger-full-access)
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
