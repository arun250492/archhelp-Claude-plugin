# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report security issues by emailing **arun250492@gmail.com** .
You will receive a response within **72 hours**.

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

We follow a **90-day responsible disclosure** policy.

## Security Design

### Prompt-injection protection

This plugin fetches source code from GitHub repositories.  Malicious
repository owners could embed adversarial instructions in their source
files.

**Mitigations applied:**

1. **No raw content in tool responses** — raw file text is consumed
   inside `analyzer.py` and converted to structured data (model names,
   route paths, import graphs).  Only synthesised Mermaid diagrams are
   returned to the model.

2. **Strict input validation** — repo identifiers are validated against
   GitHub's own naming rules before any network request is made
   (`security.py: validate_repo_identifier`).  Inputs exceeding length
   limits or containing disallowed characters are rejected.

3. **Output is data, not instructions** — every tool response is either
   a Mermaid code block (rendered as a diagram) or a structured
   Markdown table.  Neither format is interpreted as executable
   instructions by Claude.

### Network security

- All GitHub API requests use HTTPS.
- The `GITHUB_TOKEN`, if set, is read from the environment and never
  logged or included in tool responses.
- No user data is stored or transmitted to any third party.

### Rate-limit handling

- The client retries on 429 / 403 responses, respecting `Retry-After`
  headers (capped at 60 seconds).
- Without a `GITHUB_TOKEN` the GitHub API allows 60 unauthenticated
  requests per hour.  Authentication raises this to 5,000 per hour.
