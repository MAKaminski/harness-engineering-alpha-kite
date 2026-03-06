# Security Policy

## Supported Versions

Security updates are applied to the current main branch. We do not maintain separate release branches for older versions.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities in public issues, discussions, or pull requests.**

If you believe you have found a security issue in Symphony:

1. **Report privately**  
   Open a GitHub Security Advisory for this repository (Security → Advisories → **Report a vulnerability**), or contact the maintainers through a private channel if you have one.

2. **Include**  
   - Description of the issue and impact  
   - Steps to reproduce (or a proof-of-concept)  
   - Affected versions or commit range  
   - Any suggested fix or mitigation, if you have one  

3. **What to expect**  
   We will acknowledge your report and respond as soon as we can. We may ask for clarification. We will keep you updated on status and credit you in the advisory if you wish, unless you prefer to remain anonymous.

4. **Disclosure**  
   We aim to fix critical issues promptly and coordinate disclosure with you. We will not disclose the issue publicly before a fix is available without your agreement.

## Security Considerations for Deployments

- **Trust boundary**: This implementation is intended for **trusted environments**. The default posture uses auto-approved agent actions; do not expose it on untrusted networks without additional hardening.
- **Secrets**: Use environment variables (e.g. `$LINEAR_API_KEY`) for API keys; do not commit tokens to the repository.
- **Workspace isolation**: Workspaces are per-issue and under a configurable root; ensure the workspace root has appropriate permissions and is not writable by untrusted users.
- **Hooks**: `WORKFLOW.md` hooks run as shell scripts with the same privileges as the Symphony process; only use workflow files and hooks from trusted sources.

For more operational safety guidance, see the specification (SPEC.md) and README.
