# Security policy

## Supported versions

| Version | Supported |
|---|---|
| latest `v*` tag / `main` | Yes |
| older tags | No — please upgrade |

## Reporting a vulnerability

**Do not open a public issue.** Email the maintainer or use GitHub's
private vulnerability reporting on the repo's Security tab. Include:

- what the app was doing (installing, loading catalog, …)
- the log-area output if relevant (redact any personal paths)
- distro, Python version, install scope (user/system)

You will get a first response within 7 days. Fixes ship in a patch release
with a CHANGELOG entry crediting the reporter (unless anonymity is asked).

## Scope notes

This app executes `flatpak install` for apps the user explicitly confirmed,
shows the exact command beforehand, and never uninstalls anything on its
own. Anything that breaks those guarantees (silent installs, command
injection through app metadata, running unexpected binaries) is treated as
a security bug.
