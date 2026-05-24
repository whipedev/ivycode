# Security Policy

## Supported versions

While **ivycode** is in pre-alpha (`0.x`), only the latest minor release
receives security updates.

| Version | Supported |
|---------|-----------|
| latest `0.x` | ✅ |
| older `0.x`  | ❌ |

Once we reach `1.0`, the support matrix will be expanded.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Please report vulnerabilities privately through GitHub's built-in
**Private Vulnerability Reporting**:

1. Open <https://github.com/whipedev/ivycode/security/advisories/new>.
2. Fill in: what is vulnerable, how to reproduce, impact, suggested fix
   (if any).
3. We will respond within **5 business days** with an acknowledgement and
   an initial assessment.
4. Once a fix is ready, a coordinated disclosure timeline will be agreed
   with the reporter.

## Scope

In scope:

- The `ivycode` Python package (CLI, agents, providers, codegraph,
  skills, ui, gateway).
- The optional local Gateway (FastAPI shim).
- Documented configuration formats (`config.toml`, environment variables).

Out of scope:

- Vulnerabilities in upstream dependencies — please report to the
  respective project.
- Issues that require physical access to an unlocked developer machine.
- Behaviour that requires the user to disable documented safety gates
  (e.g. forcing `verify_tls=false` on a public host).

## Hall of fame

Credited reporters of valid issues will be listed in this section after
the fix is released.
