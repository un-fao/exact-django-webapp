# Security Policy

## Reporting a Vulnerability

The EX-ACT team and the FAO CSI (Chief Statistician's and Information Office) take the security of this project seriously.

If you believe you have found a security vulnerability in EX-ACT, please report it to us privately. **Do not open a public GitHub issue.**

### How to Report

Send an email to **exact@fao.org** with the subject line `[SECURITY] <short description>` and include:

- A description of the vulnerability and its potential impact
- Steps to reproduce the issue
- The affected version(s), commit hash, or environment (dev / review / production)
- Any proof-of-concept code, logs, or screenshots
- Your name and contact details (optional — you may report anonymously)

### What to Expect

- **Acknowledgement** within 5 business days confirming receipt of your report
- **Initial assessment** within 10 business days with a preliminary severity rating (CVSS v3.1)
- **Remediation timeline** shared once the root cause is confirmed
- **Coordinated disclosure** — we will agree with you on a public disclosure date after the fix is deployed

## Supported Versions

Security fixes are backported only to the latest minor release. Older versions are supported on a best-effort basis.

| Version | Supported |
| ------- | --------- |
| Latest (main) | ✅ |
| Previous minor | ⚠️ Best effort |
| Older | ❌ |

## Scope

In scope:

- The Django REST API (`djangoexact/`)
- Deployment configuration (`gcp-deployment/`, `.github/workflows/`)
- Frontend assets bundled in the repository

Out of scope:

- Third-party services (Firebase, GCP, FAOSTAT) — report those directly to the respective vendor
- Social engineering of FAO staff
- Physical attacks against FAO infrastructure

## Safe Harbor

We will not pursue legal action against researchers who:

- Make a good-faith effort to avoid privacy violations, data destruction, and service disruption
- Give us reasonable time to fix the issue before any public disclosure
- Do not exploit the vulnerability beyond what is necessary to demonstrate it
