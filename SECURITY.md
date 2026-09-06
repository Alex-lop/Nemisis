# Security

Nemisis executes repository code in local worker processes. Local mode is for a trusted checkout;
it is not a sandbox for hostile code. The full trust boundary, what the controller owns, and what a
candidate cannot influence are in [docs/SECURITY.md](docs/SECURITY.md).

## Reporting a vulnerability

Please report privately through
[GitHub Security Advisories](https://github.com/Alex-lop/Nemisis/security/advisories/new) rather
than a public issue. Include the handler or input that demonstrates the problem and the verdict you
observed. A report that shows CrashCheck issuing `FIX_PROVEN_FOR_THIS_CAPSULE` for a handler that
loses or duplicates money is the most valuable kind and will be treated as a bug in the checker,
not in the handler.

## Scope

- In scope: any way to earn a verdict the durable state does not support, any way for candidate
  code to influence probes, kill points, labels, or verdict logic, and any credential leaking into
  a receipt, manifest, report, or log.
- Documented boundary, not a vulnerability: a handler that forks a new session and closes the
  worker's pipes can outlive the kill; a handler that forges the store's private IPC channel can
  misreport commits. Both are hostile code in a mode that assumes a trusted checkout.
