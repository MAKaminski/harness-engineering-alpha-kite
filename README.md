# Symphony (Python)

A long-running service that orchestrates coding agents from an issue tracker (Linear). It reads work from Linear, creates per-issue workspaces, and runs a Codex app-server agent for each issue. Implements the [Symphony Service Specification](SPEC.md).

## Features

- **Workflow loader**: `WORKFLOW.md` with YAML front matter and Jinja2 prompt template
- **Config layer**: Typed getters, `$VAR` env resolution, path expansion
- **Linear client**: GraphQL client for candidate issues, state refresh, terminal cleanup
- **Workspace manager**: Per-issue directories, sanitized keys, hooks (`after_create`, `before_run`, `after_run`, `before_remove`)
- **Agent runner**: Codex app-server protocol over stdio (initialize, thread/start, turn/start, streaming)
- **Orchestrator**: Poll loop, dispatch, reconciliation, retry with exponential backoff, stall detection
- **Optional HTTP server**: Dashboard at `/`, JSON API at `/api/v1/state` and `/api/v1/refresh`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Set your Linear API key and project:

```bash
export LINEAR_API_KEY=lin_api_...
```

Edit `WORKFLOW.md` and set `tracker.project_slug` to your Linear project’s slug ID (from the project URL or API).

## Run

```bash
# Default: use ./WORKFLOW.md
python -m symphony.cli

# Explicit workflow path
python -m symphony.cli /path/to/WORKFLOW.md

# With optional dashboard on port 8080
python -m symphony.cli --port 8080

# Verbose logs
python -m symphony.cli -v
```

The service will:

1. Validate workflow and config
2. Clean up workspaces for issues already in terminal states
3. Poll Linear on the configured interval for issues in active states
4. Dispatch agents (respecting concurrency and blocker rules)
5. Reconcile running issues each tick (stop if issue moved to terminal/non-active)
6. Schedule retries on failure with exponential backoff

## Workflow file

See `WORKFLOW.md` in this repo for an example. Required:

- `tracker.kind`: `linear`
- `tracker.api_key`: token or `$LINEAR_API_KEY`
- `tracker.project_slug`: Linear project slug
- `codex.command`: e.g. `codex app-server`

Prompt body supports `{{ issue.* }}` and `{% if attempt %}...{% endif %}` (Jinja2).

## Trust and safety

This implementation is intended for **trusted environments**. It uses a high-trust posture:

- **Approvals**: Auto-approve command and file-change approvals
- **User input**: Treat user-input-required as hard failure (no indefinite stall)
- **Sandbox**: Uses Codex sandbox settings from workflow (`thread_sandbox`, `turn_sandbox_policy`)

Do not expose the dashboard or API on an untrusted network without additional hardening.

## License

As per project.
