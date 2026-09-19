# Security Policy

## Reporting

Open a private security advisory or contact the maintainer privately before disclosing vulnerabilities.

## Deployment Warnings

- Never expose `/api/*` or `/data/*` without backend authentication.
- Never publish `.env`, `data/`, logs, generated sites, PM2 dumps, or Caddy basic-auth hashes.
- Rotate any token that has appeared in logs, process environments, shell history, screenshots, or chat transcripts.
- Generated sites should be isolated from admin UI storage using a separate domain/origin.
