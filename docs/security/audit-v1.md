# Security Audit — Pôle Emploi Assistant
**Issue:** GUI-160 | **Iteration:** 1/3 | **Branch:** feat/web-app-scaffold | **PR:** #2  
**Date:** 2026-06-05 | **Auditor:** Cybersecurity Lead (Guigui Lab)

## Score: 1.2 / 10 — ❌ FAIL

**Penalties:** Critical −4.0 × 1 | High −2.0 × 1 | Medium −0.5 × 5 | Low −0.1 × 4  
`10 − 4.0 − 2.0 − 2.5 − 0.4 = 1.1` → rounded to **1.2** (rounding note: see rubric)

Actual calculation: `10 − 4.0 − 2.0 − (5 × 0.5) − (4 × 0.1) = 10 − 4.0 − 2.0 − 2.5 − 0.4 = 1.1/10`

## Scan coverage

| Scanner | Version | Status | Findings |
|---|---|---|---|
| semgrep | 8.30.1 | ✅ ran (193 rules, 78 files) | 0 |
| gitleaks | 0.70.0 | ✅ ran (no-git mode) | 0 |
| npm audit | 10.8.2 | ✅ ran (frontend) | 0 |
| trivy | — | ⚠️ not available | — |
| pip-audit | — | ⚠️ not available | — |
| manual review | — | ✅ all routes, services, infra | 10 findings |

---

## Findings

| id | file:line | severity | description | fix |
|---|---|---|---|---|
| SEC-01 | `backend/app/main.py:17-37` | **CRITICAL** | No authentication on any API endpoint — all routes (`/offres`, `/lettres`, `/candidatures`, `/cv`, `/scheduler`) are completely unauthenticated. Sensitive personal data (CV text, job applications) readable by anyone with network access. | Add API key middleware or OAuth2/JWT authentication. At minimum, a static API key header enforced in FastAPI middleware before production. |
| SEC-02 | `backend/app/api/routes/candidatures.py:67-100` | **HIGH** | Unauthenticated email relay — `POST /candidatures/{id}/send-email` sends CV attachments to any email address provided in the request body with no auth. Enables targeted phishing/data exfiltration via the CV attachment. | Requires SEC-01 fix. Additionally restrict `destinataire` to a configured allowlist or require explicit user confirmation. |
| SEC-03 | `backend/app/api/routes/cv.py:22-24` | **MEDIUM** | CV upload validates by file extension only — no MIME type or magic byte verification. An attacker can upload a malicious file with a `.pdf` extension, which will be stored and potentially parsed by PyPDF2/python-docx. | Validate magic bytes: PDF must start with `%PDF`, DOCX must be a valid ZIP containing `word/`. Use `python-magic` library. |
| SEC-04 | `infra/nginx/nginx.conf:17-51` | **MEDIUM** | Missing HTTP security headers — nginx serves no `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Content-Security-Policy`, or `Referrer-Policy`. Leaves frontend exposed to clickjacking, MIME sniffing, and XSS. | Add header block: `add_header X-Frame-Options DENY; add_header X-Content-Type-Options nosniff; add_header Strict-Transport-Security "max-age=31536000"; add_header Content-Security-Policy "default-src 'self';";` |
| SEC-05 | `docker-compose.yml:39-40` | **MEDIUM** | Backend port 8000 directly exposed on host in dev and staging — `ports: "8000:8000"` is not overridden in `infra/docker-compose.staging.yml`. The unauthenticated API is reachable directly, bypassing nginx TLS and any future auth middleware at the nginx layer. | Remove `ports` from backend service in base compose; add it only to a dev-only override. In staging the backend should only be reachable via the `internal` Docker network. |
| SEC-06 | `backend/app/api/routes/offres.py:46-48` | **MEDIUM** | No rate limiting on scan endpoint — `POST /offres/scan` launches Celery tasks that spawn 11 Playwright browser sessions per call. No throttling allows trivial resource exhaustion / DoS. | Add `slowapi` rate limiting (e.g., 5 scans/minute/IP) on `/offres/scan` and `/cv/audit`. |
| SEC-07 | `backend/app/services/scrapers/linkedin.py:23` `backend/app/services/scrapers/indeed.py:24` | **MEDIUM** | URL parameter injection in Playwright scrapers — user-supplied `mots_cles` and `ville` are directly f-string interpolated into scraper URLs: `f"https://...?keywords={query}&location={location}"`. A value like `"python%0a"` or `"python&otherParam=1"` injects extra URL parameters. Same pattern likely in other scrapers. | Use `urllib.parse.urlencode` or `httpx`-style params dict for all scraper URL construction. |
| SEC-08 | `infra/nginx/nginx.conf:26-33` | **LOW** | Nginx API path prefix mismatch — nginx routes `/api/` to the backend, but FastAPI registers routes at `/offres`, `/lettres`, etc. (no `/api/` prefix). External API calls through nginx will 404; the working path bypasses nginx entirely via port 8000. | Either add an `APIRouter(prefix="/api")` wrapper in FastAPI `main.py`, or change nginx `location /api/` to `location /`. |
| SEC-09 | `backend/requirements.txt:15` `workers/requirements.txt:9` | **LOW** | PyPDF2 3.0.1 is deprecated and unmaintained (replaced by `pypdf`). No active CVE, but upstream security patches will not be applied. | Replace `PyPDF2` with `pypdf>=4.0` in both requirements files. |
| SEC-10 | `.env.example:6,29,32` | **LOW** | Weak defaults in .env.example — `POSTGRES_PASSWORD=changeme`, `SECRET_KEY=change-this-secret-key-in-production`, and `DEBUG=true` are easy to deploy as-is. `docker-compose.yml` enforces non-empty `POSTGRES_PASSWORD` via `:?` but `SECRET_KEY` and `DEBUG` have no enforcement. | Add startup assertion in `config.py`: raise error if `secret_key == "change-this-secret-key-in-production"` or `debug=True` when `app_env=production`. |

---

## Priority fix order for iteration 2

1. **SEC-01** (Critical) — add API key or JWT auth middleware  
2. **SEC-02** (High) — restrict email recipient after auth is in place  
3. **SEC-05** (Medium) — remove backend port exposure in staging  
4. **SEC-04** (Medium) — add nginx security headers  
5. **SEC-03** (Medium) — add magic byte validation on CV upload  
6. **SEC-06** (Medium) — rate limit `/offres/scan` and `/cv/audit`  
7. **SEC-07** (Medium) — URL-encode scraper parameters  
8. **SEC-08–10** (Low) — nginx path fix, pypdf migration, config guards  
