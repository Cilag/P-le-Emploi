# Security Audit — Pôle Emploi Assistant
**Issue:** GUI-162 | **Iteration:** 1/3 | **Branch:** feat/web-app-scaffold | **Date:** 2026-06-05  
**Auditor:** Cybersecurity Lead (Guigui Lab) | **Baseline:** GUI-160 audit-v1 (score 1.1/10 FAIL)

## Score: 0 / 10 — ❌ FAIL

**Penalties:** Critical −4.0 × 2 | High −2.0 × 2 | Medium −0.5 × 5 | Low −0.1 × 4  
`10 − 8.0 − 4.0 − 2.5 − 0.4 = −4.9` → clamped to **0/10**

> ⚠️ **Note:** GUI-157 (Backend hardening) is marked done but its claimed fixes are NOT present in the code on `feat/web-app-scaffold`:  
> — No `python-jose`, `bcrypt`, `slowapi`, or `python-magic` in `backend/requirements.txt`  
> — No JWT middleware or `Depends(get_current_user)` on any route  
> — No MIME validation in cv.py  
> — Email relay still sends to `req.destinataire` (no user-binding)  
> A partial GUI-157 edit also introduced a NEW critical bug (broken import in cv.py).

## Scan coverage

| Scanner | Status | Findings |
|---|---|---|
| semgrep 1.164.0 (auto ruleset) | ✅ ran (backend + frontend) | 1 (Dockerfile USER) |
| gitleaks 0.70.0 (no-git mode) | ✅ ran (full repo, 127 KB) | 0 |
| npm audit (Next.js 14.2.18) | ✅ ran (lockfile generated) | 2 (1 critical, 1 moderate) |
| pip-audit | ⚠️ failed (psycopg2-binary build — no pg_config) | n/a |
| trivy | ⚠️ not available on this host | — |
| manual review | ✅ all routes, config, infra, scrapers | 11 findings |

---

## Findings

| id | file:line | severity | description | fix |
|---|---|---|---|---|
| SEC-01 | `backend/app/main.py:17-37` | **CRITICAL** | No authentication on any API endpoint — JWT not implemented despite GUI-157. No `python-jose`/`bcrypt` in requirements. All routes (`/offres`, `/lettres`, `/candidatures`, `/cv`, `/scheduler`) are unauthenticated. Personal data (CV text, letters, candidatures) readable/writable by anyone. | Add `python-jose[cryptography]` + `bcrypt` to requirements; implement OAuth2 password-bearer middleware; add `Depends(get_current_user)` to all non-health routes. |
| NEW-01 | `frontend/package.json:2` | **CRITICAL** | Next.js 14.2.18 has Authorization Bypass in Middleware (GHSA-f82v-jwr5-mffw) — attacker can bypass auth middleware entirely. Also includes SSRF in rewrites (GHSA-4342-x723-ch2f), XSS in CSP nonce handling (GHSA-ffhc-5mcf-pf4q), and 20+ additional CVEs (DoS, cache poisoning). npm audit: 1 critical. | Upgrade `next` to ≥ 15.2.4 in `package.json`. |
| SEC-02 | `backend/app/api/routes/candidatures.py:94` | **HIGH** | Unauthenticated email relay — `POST /candidatures/{id}/send-email` sends CV+letter PDF to any `req.destinataire` with no auth and no ownership check. Enables targeted phishing/CV exfiltration. | Requires SEC-01. After auth: restrict `destinataire` to `current_user.email` only. |
| NEW-02 | `backend/app/api/routes/cv.py:9,32-33,36` | **HIGH** | Broken import crashes FastAPI on startup — `from app.core.config import settings` references a non-existent `app/core/` package. Additionally `settings.UPLOAD_DIR` (lines 32-36) does not match the actual attribute name `upload_dir` defined in `app/config.py`. The entire app fails to start once the CV router is included. | Change import to `from app.config import settings`; replace `settings.UPLOAD_DIR` with `settings.upload_dir`. |
| SEC-03 | `backend/app/api/routes/cv.py:22-24` | **MEDIUM** | CV upload validates by file extension only — `python-magic` absent from requirements. Attacker can upload malicious file with `.pdf` extension for stored parsing by PyPDF2/python-docx. | Add `python-magic` to requirements; validate magic bytes: PDF must start with `%PDF`, DOCX must be valid ZIP containing `word/`. |
| SEC-04 | `infra/nginx/nginx.conf:16-51` | **MEDIUM** | Missing HTTP security headers — no `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Content-Security-Policy`, or `Referrer-Policy`. Frontend exposed to clickjacking, MIME sniffing, XSS amplification. | Add to the `listen 443` server block: `add_header X-Frame-Options DENY; add_header X-Content-Type-Options nosniff; add_header Strict-Transport-Security "max-age=31536000; includeSubDomains"; add_header Content-Security-Policy "default-src 'self'"; add_header Referrer-Policy no-referrer-when-downgrade;` |
| SEC-05 | `docker-compose.yml:39-40` | **MEDIUM** | Backend port 8000 still exposed on host — `ports: "8000:8000"` bypasses nginx TLS and any future auth middleware at the nginx layer. Unauthenticated API directly reachable. | Remove `ports` from backend service in base compose; add only to `docker-compose.dev.yml` override. Backend should only be reachable via the `internal` network. |
| SEC-06 | `backend/app/main.py`, `backend/app/api/routes/offres.py:45-48` | **MEDIUM** | No rate limiting — `slowapi` absent from requirements, not wired in `main.py`. `POST /offres/scan` launches 11 Playwright browser sessions per call with no throttle (trivial DoS/resource exhaustion). | Add `slowapi` to requirements; configure limiter in `main.py`; decorate `/offres/scan` and `/cv/audit` with `@limiter.limit("5/minute")`. |
| SEC-07 | `backend/app/services/scrapers/linkedin.py:23` | **MEDIUM** | URL parameter injection — user-supplied `mots_cles`/`ville` f-string interpolated directly into scraper URLs without `urllib.parse.quote()`. Same pattern across all 11 scrapers. | Use `urllib.parse.urlencode({"keywords": query, "location": location})` for all scraper URL construction. |
| SEC-08 | `infra/nginx/nginx.conf:26-33` | **LOW** | nginx `location /api/` routes to backend, but FastAPI registers routes at `/offres`, `/lettres` etc. (no `/api/` prefix). External API calls via nginx will 404; real API only reachable directly via exposed port 8000. | Either add `APIRouter(prefix="/api")` wrapper in FastAPI `main.py`, or change nginx `location /api/` to `location /`. |
| SEC-09 | `backend/requirements.txt:15` | **LOW** | `PyPDF2==3.0.1` is deprecated and unmaintained (replaced by `pypdf`). No active CVE now, but security patches will not be applied upstream. | Replace with `pypdf>=4.0`. |
| SEC-10 | `.env.example:5,29,31` | **LOW** | Weak defaults — `POSTGRES_PASSWORD=changeme`, `SECRET_KEY=change-this-secret-key-in-production`, `DEBUG=true`. No runtime enforcement prevents these from being deployed as-is. | Add startup assertion in `config.py`: raise if `secret_key` matches default value or `debug=True` when `app_env=production`. |
| NEW-03 | `backend/Dockerfile:18` | **LOW** | Containers run as root — no `USER` directive. If a process inside the container is compromised, attacker gets full container-root access. Flagged by semgrep (dockerfile.security.missing-user). | Add `RUN useradd -m appuser && chown -R appuser /app` + `USER appuser` before the `CMD` line in all Dockerfiles. |

---

## Priority fix order for iteration 2

1. **NEW-02** (High/App-breaking) — fix broken import in cv.py so app can start  
2. **NEW-01** (Critical) — upgrade Next.js ≥ 15.2.4  
3. **SEC-01** (Critical) — implement JWT auth middleware on all routes  
4. **SEC-02** (High) — restrict email relay to `current_user.email` after auth  
5. **SEC-05** (Medium) — remove backend port 8000 from base compose  
6. **SEC-04** (Medium) — add nginx security headers  
7. **SEC-03** (Medium) — add python-magic MIME validation  
8. **SEC-06** (Medium) — add slowapi rate limiting  
9. **SEC-07** (Medium) — URL-encode all scraper parameters  
10. **SEC-08–10, NEW-03** (Low) — nginx path, pypdf migration, config guards, Docker USER  
