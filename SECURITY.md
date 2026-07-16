# Security Policy

Sisyphus is an experimental repository-local control plane. It has not published
a supported production release. Security fixes are applied to `main` on a
best-effort basis until a tagged support policy replaces this document.

## Reporting

Do not disclose suspected vulnerabilities in a public issue, discussion, pull
request, or chat transcript.

Use GitHub's private vulnerability reporting flow from the repository
`Security` tab when it is available. If that flow is unavailable, contact the
repository owner through their GitHub profile without including exploit details
and request a private reporting channel.

Include:

- affected commit or version
- reproduction steps
- expected and observed security boundaries
- impact and files or data at risk
- any known workaround

Relevant reports include repository path escapes, authorization bypasses,
unexpected command execution, secret exposure, unsafe external notifications,
and task or evidence integrity failures. General bugs and feature requests are
not security reports.

## Disclosure

Allow the maintainer time to reproduce and correct a report before public
disclosure. There is currently no guaranteed response or remediation SLA.
