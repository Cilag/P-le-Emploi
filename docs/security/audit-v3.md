# Security Audit — GUI-162 — Iteration 2/3 (v3)

**Date:** 2026-06-05  
**Auditor:** Cybersecurity Lead (ac3330c6)  
**Ref PR:** [GUI-164] https://github.com/Cilag/P-le-Emploi/pull/10 (`backend/GUI-164-security-fixes`)  
**Ref v2:** docs/security/audit-v2.md (score 9.0/10 PASS)  
**Score: 7.3 / 10 — FAIL ❌**

---

## Scan coverage

| Scanner | Target | Status |
|---------|--------|--------|
| gitleaks 8.x (--no-git) | entire repo | ✅ ran — 0 leaks found |
| semgrep p/python (HOME=/tmp) | backend/ | ✅ ran — 0 findings |
| trivy fs (fresh DB 2026-06-05) | entire repo | ✅ ran — findings below |
| pip-audit | backend/requirements.txt | ✅ ran — 0 findings (DB lag vs trivy) |
| pip-audit | workers/requirements.txt | ✅ ran — 0 findings (DB lag vs trivy) |
| manual diff review | PR #10 changes | ✅ ran |

---

## v2 Fix Verification

All 7 targeted fixes in PR #10 are confirmed in the diff:

| ID | Fix | Status | Evidence |
|----|-----|--------|----------|
| SEC-02 | Email relay — restrict destinataire to settings.user_email | ✅ FIXED | `candidatures.py:86-91`: 403 if `req.destinataire != settings.user_email` |
| SEC-05 | Remove `ports: 8000:8000` from docker-compose.yml | ✅ FIXED | docker-compose.yml diff: lines `- "8000:8000"` removed |
| SEC-06 | Rate limit 5/min on /offres/scan + /cv/audit | ✅ FIXED | `app/core/limiter.py` added; `@limiter.limit("5/minute")` on both routes |
| SEC-07 | URL-encode scraper query params (7 scrapers) | ✅ FIXED | `urllib.parse.quote_plus` applied in cadremploi, hellowork, indeed, letudiant, linkedin, monster; `quote(safe='-')` in regionsjob |
| SEC-09 | PyPDF2 → pypdf>=4.0.0 | ✅ FIXED | `backend/requirements.txt` + `workers/requirements.txt` + `cv_parser.py` import updated |
| SEC-10 | Startup RuntimeError if default SECRET_KEY in production | ✅ FIXED | `main.py:18-23`: `raise RuntimeError` if `app_env==production` and `secret_key=="dev-secret-change-me"` |
| NEW-03 | Non-root appuser in Dockerfile (dev + prod stages) | ✅ FIXED | `useradd` moved to base stage; `USER appuser` in both dev and prod targets |
| SEC-01 | JWT auth on all protected routes | ✅ pre-existing PASS | Unchanged, verified via grep |
| SEC-03 | MIME magic bytes validation on CV upload | ✅ pre-existing PASS | `cv.py:46-50`: python-magic check intact |

---

## Open Findings

| id | file:line | severity | fix |
|----|-----------|----------|-----|
| NEW-01 | `backend/app/main.py:32-33` | MEDIUM | Disable docs/redoc in production: `docs_url=None if settings.app_env=="production" else "/docs"` (same for redoc_url) |
| SEC-08 | `infra/nginx/nginx.conf` | LOW | nginx only proxies `/api/` and `/auth/` to backend; routes `/offres`, `/lettres`, `/candidatures`, `/cv` fall through to frontend. Add dedicated `location` blocks or prefix all FastAPI routes with `/api/`. |
| DEP-01 | `backend/requirements.txt:16` | MEDIUM | python-multipart 0.0.19: CVE-2026-24486 + CVE-2026-42561 (path traversal arbitrary file write, fix 0.0.27); app-level `os.path.realpath()` in cv.py provides partial mitigation — upgrade to `python-multipart>=0.0.27` |
| DEP-02 | `backend/requirements.txt:8` | MEDIUM | python-jose 3.3.0: CVE-2024-33663 (CRITICAL algo confusion with ECDSA — not exploitable, app uses HS256) + CVE-2024-33664 (MEDIUM DoS exploitable via malformed JWT input) — upgrade to `python-jose>=3.4.0` |
| DEP-03 | `workers/requirements.txt:7` | MEDIUM | aiohttp 3.11.10: CVE-2025-69223 HIGH (zip bomb via auto_decompress from scraped content) — workers parse external HTTP responses; upgrade to `aiohttp>=3.13.3` |
| DEP-04 | `workers/requirements.txt:11` | MEDIUM | lxml 5.3.0: CVE-2026-41066 HIGH (info disclosure via untrusted XML/HTML — workers parse HTML from scraped job sites which is untrusted input) — upgrade to `lxml>=6.1.0` |
| DEP-05 | `backend/requirements.txt:14` + `workers/requirements.txt:14` | LOW | python-dotenv 1.0.1: CVE-2026-28684 (symlink-following arbitrary file overwrite); low risk in containerized environment — upgrade to `python-dotenv>=1.2.2` |

**Note on DEP-01 through DEP-05:** These are pre-existing vulnerabilities not introduced by PR #10. First detected in this iteration via trivy (trivy was not run in previous iterations).

---

## Scoring

| Severity | Count | Penalty |
|----------|-------|---------|
| Critical | 0 | −0.0 |
| High | 0 | −0.0 |
| Medium | 5 (NEW-01, DEP-01, DEP-02, DEP-03, DEP-04) | −2.5 |
| Low | 2 (SEC-08, DEP-05) | −0.2 |
| **Total** | **7** | **−2.7** |

`score = max(0, 10 − 2.7) = **7.3 / 10**`

**Verdict: FAIL ❌ (< 8/10)**

---

## Fix priority for iteration 3

1. **DEP-01** — Upgrade `python-multipart>=0.0.27` in `backend/requirements.txt` *(5 min, no code change)*
2. **DEP-02** — Upgrade `python-jose>=3.4.0` in `backend/requirements.txt` *(5 min, no code change)*
3. **DEP-03** — Upgrade `aiohttp>=3.13.3` in `workers/requirements.txt` *(5 min, no code change)*
4. **DEP-04** — Upgrade `lxml>=6.1.0` in `workers/requirements.txt` *(5 min, no code change)*
5. **NEW-01** — Gate `/docs`+`/redoc` behind `app_env != "production"` in `main.py` *(10 min)*
6. **DEP-05** — Upgrade `python-dotenv>=1.2.2` in both requirements files *(5 min)*
7. **SEC-08** — nginx routing alignment *(requires discussion with Web Lead on prefix strategy)*

Resolving DEP-01 through DEP-05 + NEW-01 removes all Medium findings and both Low findings, giving:
`10 − 0.1 (SEC-08 LOW) = 9.9/10 → PASS`
