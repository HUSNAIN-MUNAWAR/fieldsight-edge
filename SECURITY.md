# Security Policy

## Supported use

FieldSight Edge is a public reference implementation with a deterministic local demo mode. It includes security-oriented controls, but it is not presented as a hosted production service or as a compliance-certified platform.

## Reporting a vulnerability

- Prefer a private GitHub security advisory for vulnerabilities that could expose users, secrets, or infrastructure.
- If private reporting is unavailable, open a minimal public issue without exploit details and note that you are requesting a private follow-up channel.
- Do not include credentials, tokens, local file paths, or proof-of-concept payloads that would create additional risk for maintainers or users.

## What helps a report

- A clear description of the affected component or route.
- Reproduction steps.
- Expected versus actual behavior.
- Impact assessment and any safe mitigation ideas.

## Scope notes

Reports about documented but intentionally unconfigured boundaries, such as optional CMMS, ERP, GIS, cloud storage, Slack, email, or external model providers, should explain the exact configuration assumption that makes the issue relevant.
