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

**Codex CLI:** Symphony runs `codex app-server` per issue. Install the Codex app-server CLI and ensure it is on your PATH (or set `codex.command` in `WORKFLOW.md` to the full path, e.g. `/usr/local/bin/codex app-server`). Verify with:
```bash
bash -lc "codex app-server"
```
(No "command not found" and the process should stay running.)

Set your Linear API key and project:

```bash
export LINEAR_API_KEY=lin_api_...
export LINEAR_PROJECT_SLUG=your-project-slug   # from project URL, e.g. alpha-kite-f0ebf2d85f93
```

Or set `tracker.project_slug` in `WORKFLOW.md`; `$LINEAR_PROJECT_SLUG` is expanded from the environment.

## Run

```bash
# Recommended: use the run script (checks env, starts with dashboard on :8080)
./scripts/run-symphony.sh

# Or manually (use python3 if python is not available):
python3 -m symphony.cli -v --port 8080

# Default: use ./WORKFLOW.md
python3 -m symphony.cli

# Explicit workflow path
python3 -m symphony.cli /path/to/WORKFLOW.md
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
