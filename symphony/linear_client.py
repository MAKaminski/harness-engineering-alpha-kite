"""Linear issue tracker client (SPEC.md Section 11). GraphQL with auth, pagination, normalization."""
from __future__ import annotations

import json
from typing import Any

import requests

from .config import ServiceConfig
from .models import BlockerRef, Issue


LINEAR_GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"
PAGE_SIZE = 50
REQUEST_TIMEOUT = 30


class LinearClientError(Exception):
    def __init__(self, code: str, message: str, details: Any = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _gql(endpoint: str, api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    # Linear API keys (lin_api_...) must be sent as-is; do not use "Bearer " prefix (API returns 400).
    auth_header = (api_key or "").strip()
    if auth_header and not auth_header.lower().startswith("bearer ") and not auth_header.startswith("lin_api_"):
        auth_header = f"Bearer {auth_header}"
    elif auth_header and auth_header.startswith("lin_api_"):
        pass  # use as-is
    resp = requests.post(
        endpoint,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        raise LinearClientError(
            "linear_api_status",
            f"HTTP {resp.status_code}",
            details=resp.text[:500],
        )
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise LinearClientError(
            "linear_graphql_errors",
            "GraphQL errors",
            details=data.get("errors"),
        )
    return data


def _normalize_issue(node: dict[str, Any]) -> Issue:
    """Map Linear issue node to normalized Issue (Section 4.1.1, 11.3)."""
    state_obj = node.get("state") or {}
    state_name = (state_obj.get("name") or "").strip() or "Unknown"
    priority = node.get("priority")
    if priority is not None and not isinstance(priority, int):
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = None
    labels_raw = node.get("labels", {}).get("nodes", []) if isinstance(node.get("labels"), dict) else (node.get("labels") or [])
    labels = [str(l.get("name", "")).strip().lower() for l in labels_raw if l and l.get("name")]

    # Blocked by: inverse relation "blocks" (issues that block this one)
    # API returns "relations" (relatedIssues was deprecated/removed)
    blocked_by: list[BlockerRef] = []
    relations_data = node.get("relations") or node.get("relatedIssues") or {}
    for rel in relations_data.get("nodes", []) or []:
        if not isinstance(rel, dict):
            continue
        link = rel.get("relatedIssue") or rel
        if not isinstance(link, dict):
            continue
        # If relation type is "blocked" then this issue is blocked by link; if "blocks" then link blocks this
        relation_type = (rel.get("type") or "").lower()
        if relation_type in ("blocked", "blocks"):
            other = link
            other_state = (other.get("state") or {}).get("name") if isinstance(other.get("state"), dict) else None
            blocked_by.append(BlockerRef(
                id=other.get("id"),
                identifier=other.get("identifier"),
                state=other_state,
            ))

    # Fallback: some APIs expose block relations differently
    if not blocked_by and isinstance(node.get("blockedBy"), dict):
        for n in (node.get("blockedBy") or {}).get("nodes", []) or []:
            if isinstance(n, dict):
                st = (n.get("state") or {}).get("name") if isinstance(n.get("state"), dict) else None
                blocked_by.append(BlockerRef(id=n.get("id"), identifier=n.get("identifier"), state=st))

    created = node.get("createdAt")
    updated = node.get("updatedAt")
    return Issue(
        id=str(node.get("id", "")),
        identifier=str(node.get("identifier", "")),
        title=str(node.get("title", "")),
        description=node.get("description") if node.get("description") else None,
        priority=priority,
        state=state_name,
        branch_name=node.get("branchName"),
        url=node.get("url"),
        labels=labels,
        blocked_by=blocked_by,
        created_at=created,
        updated_at=updated,
    )


# GraphQL: candidate issues by project ID (active states, paginated)
CANDIDATES_BY_ID_QUERY = """
query CandidateIssuesById($projectId: ID!, $stateNames: [String!], $first: Int!, $after: String) {
  issues(
    first: $first
    after: $after
    filter: {
      project: { id: { eq: $projectId } }
      state: { name: { in: $stateNames } }
    }
  ) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      createdAt
      updatedAt
      labels { nodes { name } }
      relations(first: 50) { nodes { type relatedIssue { id identifier state { name } } } }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# GraphQL: candidate issues by project slug (active states, paginated)
CANDIDATES_QUERY = """
query CandidateIssues($projectSlug: String!, $stateNames: [String!], $first: Int!, $after: String) {
  issues(
    first: $first
    after: $after
    filter: {
      project: { slugId: { eq: $projectSlug } }
      state: { name: { in: $stateNames } }
    }
  ) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      createdAt
      updatedAt
      labels { nodes { name } }
      relations(first: 50) { nodes { type relatedIssue { id identifier state { name } } } }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def _state_name(node: dict) -> str:
    s = node.get("state")
    if isinstance(s, dict) and s.get("name"):
        return str(s["name"]).strip()
    return "Unknown"


def _extract_candidate_nodes(data: dict) -> tuple[list[dict], bool, str | None]:
    issues_data = (data.get("data") or {}).get("issues")
    if not issues_data:
        return [], False, None
    nodes = list(issues_data.get("nodes") or [])
    for n in nodes:
        if isinstance(n.get("state"), dict):
            n["state"] = n["state"]
        else:
            n["state"] = {"name": "Unknown"}
    page_info = issues_data.get("pageInfo") or {}
    return nodes, bool(page_info.get("hasNextPage")), page_info.get("endCursor")


def fetch_candidate_issues(config: ServiceConfig) -> list[Issue]:
    """Return issues in active states for the configured project (paginated)."""
    if not config.tracker_api_key:
        raise LinearClientError("missing_tracker_api_key", "Linear API key not set")
    use_id = bool(config.tracker_project_id)
    if not use_id and not config.tracker_project_slug:
        raise LinearClientError("missing_tracker_project_slug", "Project slug or project_id not set")
    endpoint = config.tracker_endpoint or LINEAR_GRAPHQL_ENDPOINT
    state_names = config.tracker_active_states or ["Todo", "In Progress"]
    all_nodes: list[dict] = []
    after: str | None = None
    query = CANDIDATES_BY_ID_QUERY if use_id else CANDIDATES_QUERY
    while True:
        variables: dict[str, Any] = {
            "stateNames": state_names,
            "first": PAGE_SIZE,
        }
        if use_id:
            variables["projectId"] = config.tracker_project_id
        else:
            variables["projectSlug"] = config.tracker_project_slug
        if after:
            variables["after"] = after
        data = _gql(endpoint, config.tracker_api_key, query, variables)
        nodes, has_next, end_cursor = _extract_candidate_nodes(data)
        for n in nodes:
            if isinstance(n.get("state"), dict):
                n["state"] = n["state"]
            else:
                n["state"] = {"name": n.get("state", "Unknown")}
        all_nodes.extend(nodes)
        if not has_next or not end_cursor:
            break
        after = end_cursor
    return [_normalize_issue(n) for n in all_nodes]


# Terminal issues for startup cleanup (by project ID)
TERMINAL_ISSUES_BY_ID_QUERY = """
query TerminalIssuesById($stateNames: [String!], $projectId: ID!, $first: Int!, $after: String) {
  issues(
    first: $first
    after: $after
    filter: {
      state: { name: { in: $stateNames } }
      project: { id: { eq: $projectId } }
    }
  ) {
    nodes { id identifier state { name } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# Terminal issues for startup cleanup (by project slug)
TERMINAL_ISSUES_QUERY = """
query TerminalIssues($stateNames: [String!], $projectSlug: String, $first: Int!, $after: String) {
  issues(
    first: $first
    after: $after
    filter: {
      state: { name: { in: $stateNames } }
      project: { slugId: { eq: $projectSlug } }
    }
  ) {
    nodes { id identifier state { name } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def fetch_issues_by_states(config: ServiceConfig, state_names: list[str]) -> list[Issue]:
    """Used for startup terminal cleanup. Returns issues in given states (e.g. terminal) for the configured project."""
    if not state_names:
        return []
    if not config.tracker_api_key:
        raise LinearClientError("missing_tracker_api_key", "Linear API key not set")
    endpoint = config.tracker_endpoint or LINEAR_GRAPHQL_ENDPOINT
    use_id = bool(config.tracker_project_id)
    query = TERMINAL_ISSUES_BY_ID_QUERY if use_id else TERMINAL_ISSUES_QUERY
    all_nodes: list[dict] = []
    after: str | None = None
    while True:
        variables: dict[str, Any] = {"stateNames": state_names, "first": PAGE_SIZE}
        if use_id:
            variables["projectId"] = config.tracker_project_id
        else:
            variables["projectSlug"] = config.tracker_project_slug or ""
        if after:
            variables["after"] = after
        data = _gql(endpoint, config.tracker_api_key, query, variables)
        issues_data = (data.get("data") or {}).get("issues")
        if not issues_data:
            break
        nodes = list(issues_data.get("nodes") or [])
        for n in nodes:
            if isinstance(n.get("state"), dict):
                pass
            else:
                n["state"] = {"name": n.get("state", "Unknown")}
        all_nodes.extend(nodes)
        page_info = issues_data.get("pageInfo") or {}
        if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
            break
        after = page_info["endCursor"]
    return [_normalize_issue(n) for n in all_nodes]


# State refresh by issue IDs (reconciliation)
ISSUE_STATES_BY_IDS_QUERY = """
query IssueStatesByIds($issueIds: [ID!]!) {
  issues(filter: { id: { in: $issueIds } }) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      createdAt
      updatedAt
      labels { nodes { name } }
      relations(first: 50) { nodes { type relatedIssue { id identifier state { name } } } }
    }
  }
}
"""


def fetch_issue_states_by_ids(config: ServiceConfig, issue_ids: list[str]) -> list[Issue]:
    """Fetch current state for given issue IDs (reconciliation)."""
    if not issue_ids:
        return []
    if not config.tracker_api_key:
        raise LinearClientError("missing_tracker_api_key", "Linear API key not set")
    endpoint = config.tracker_endpoint or LINEAR_GRAPHQL_ENDPOINT
    data = _gql(endpoint, config.tracker_api_key, ISSUE_STATES_BY_IDS_QUERY, {"issueIds": issue_ids})
    issues_data = (data.get("data") or {}).get("issues")
    nodes = list((issues_data or {}).get("nodes") or [])
    for n in nodes:
        if isinstance(n.get("state"), dict):
            pass
        else:
            n["state"] = {"name": n.get("state", "Unknown")}
    return [_normalize_issue(n) for n in nodes]


# --- Issue state transition helper (used by local Codex server) ---
ISSUE_TEAM_QUERY = """
query IssueTeam($id: ID!) {
  issue(id: $id) {
    id
    team { id }
  }
}
"""

WORKFLOW_STATES_BY_TEAM_QUERY = """
query WorkflowStatesByTeam($teamId: ID!) {
  workflowStates(filter: { team: { id: { eq: $teamId } } }) {
    nodes {
      id
      name
    }
  }
}
"""

ISSUE_UPDATE_STATE_MUTATION = """
mutation IssueSetState($id: ID!, $stateId: String!) {
  issueUpdate(id: $id, input: { stateId: $stateId }) {
    success
    issue {
      id
      state { name }
    }
  }
}
"""


def transition_issue_to_state(endpoint: str, api_key: str, issue_id: str, state_name: str) -> None:
    """Transition a Linear issue to the given workflow state name.

    This helper is intentionally low-level so it can be called from the local Codex server
    using only env configuration (endpoint + api key + issue id + target state name).
    """
    if not issue_id:
        raise LinearClientError("missing_issue_id", "Issue ID not provided")
    if not api_key:
        raise LinearClientError("missing_tracker_api_key", "Linear API key not set")

    endpoint_norm = (endpoint or LINEAR_GRAPHQL_ENDPOINT).strip() or LINEAR_GRAPHQL_ENDPOINT
    # 1) Fetch issue to get its team
    issue_data = _gql(endpoint_norm, api_key, ISSUE_TEAM_QUERY, {"id": issue_id})
    issue_node = (issue_data.get("data") or {}).get("issue") or {}
    team = issue_node.get("team") or {}
    team_id = team.get("id")
    if not team_id:
        raise LinearClientError("missing_team", "Issue does not have an associated team")

    # 2) Fetch workflow states for that team and find the target by name (case-insensitive)
    states_data = _gql(endpoint_norm, api_key, WORKFLOW_STATES_BY_TEAM_QUERY, {"teamId": team_id})
    ws = (states_data.get("data") or {}).get("workflowStates") or {}
    nodes = list(ws.get("nodes") or [])
    target_state_name = (state_name or "").strip().lower()
    target = next(
        (s for s in nodes if isinstance(s, dict) and (s.get("name") or "").strip().lower() == target_state_name),
        None,
    )
    if not target:
        raise LinearClientError("state_not_found", f"Workflow state '{state_name}' not found for team {team_id}")
    state_id = target.get("id")
    if not state_id:
        raise LinearClientError("state_id_missing", "Workflow state ID missing for target state")

    # 3) Issue update mutation
    update_data = _gql(
        endpoint_norm,
        api_key,
        ISSUE_UPDATE_STATE_MUTATION,
        {"id": issue_id, "stateId": state_id},
    )
    payload = (update_data.get("data") or {}).get("issueUpdate") or {}
    if not payload.get("success", False):
        raise LinearClientError("issue_update_failed", "Issue state update reported success=false", details=payload)
