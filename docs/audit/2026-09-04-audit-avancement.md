# Audit d'avancement — Assistant de candidature Pôle Emploi / France Travail

**Date :** 4 septembre 2026
**Périmètre :** `origin/main` @ `4192ae2` (13 commits, dernier le 8 juin 2026) + 22 branches distantes
**Méthode :** lecture intégrale du code (backend, workers, frontend, infra, CI), exécution réelle de `pytest` et `ruff` dans un venv propre, comparaison branche par branche avec `main`.

---

## 1. Verdict en une page

Le projet a une **architecture propre et un CRUD backend solide**, mais **il ne fonctionne pas de bout en bout** : aucun parcours utilisateur ne peut être joué aujourd'hui, ni en dev, ni en staging.

| Couche | Avancement estimé | État |
|---|---|---|
| Backend — API CRUD (offres, lettres, candidatures, CV) | **80 %** | Réel, pas de stub. Manque migrations, logging, quelques bugs. |
| Backend — Auth JWT | **50 %** | Mono-utilisateur, credentials en config. Pas de table `users`. |
| Backend — Services (parsing CV, PDF, email, Gemini) | **70 %** | Implémentés. Gestion d'erreurs absente ou silencieuse. |
| Scrapers / sources d'offres | **15 %** | 1 seul sur 11 (France Travail, API OAuth officielle) est crédible. Les 10 autres visent des endpoints/sélecteurs obsolètes et échouent en silence. |
| Chaîne asynchrone (Celery workers + Beat) | **10 %** | Code écrit, **mais aucune tâche ne peut s'exécuter en Docker** (4 cassures indépendantes). |
| Frontend Next.js | **35 %** | 5 pages existent. **Aucune authentification côté client → 100 % des appels renvoient 401.** Parcours offre → lettre → candidature absent. |
| Infra / déploiement | **40 %** | Composes et nginx existent, mais le déploiement staging **lance la stack de dev** (port 8000 public, pas de TLS). |
| Tests / CI | **25 %** | CI jamais exécutée sur `main` (déclenchée sur `develop` seulement). Suite pytest cassée par son propre `conftest`. |
| Sécurité (état réel de `main`) | **≈ 3,6 / 10** | Le 9,9/10 de l'audit v4 concerne des branches **jamais fusionnées**. |
| Documentation / RGPD | **15 %** | README faux sur l'infra. Doc RGPD écrite mais non mergée. Aucun endpoint d'effacement. |

**Avancement global vers un MVP utilisable : ≈ 35–40 %.**
**Effort restant estimé : 17 à 26 jours-homme** (détail §7).

---

## 2. Ce qui fonctionne réellement

- CRUD complet et correct sur les 4 entités (`Offre`, `Lettre`, `Candidature`, `CV`), pagination offset/limit, filtres.
- Upload de CV robuste : extension, taille 10 Mo, MIME réel via `python-magic`, anti-traversée de chemin, désactivation de l'ancien CV (`backend/app/api/routes/cv.py`).
- Extraction de texte PDF (`pypdf`) et DOCX (`python-docx`) — testée avec de vrais fichiers générés.
- Génération PDF de lettre (ReportLab) et export ZIP des candidatures.
- Auth JWT HS256 + bcrypt, toutes les routes protégées (`Depends(get_current_user)`).
- Intégration **France Travail** : vrai flux OAuth2 `client_credentials`, scope `api_offresdemploiv2 o2dsoffre`, parsing JSON correct (`scrapers/france_travail.py`).
- Prompts Gemini (`gemini-1.5-flash`) soignés, en français, pour lettre et audit CV.
- Déduplication d'offres par hash SHA-256 (`titre|entreprise|ville`), bien testée (9 tests).
- Headers de sécurité nginx (HSTS, CSP, X-Frame-Options…) en staging.

---

## 3. Bloquants P0 — pourquoi rien ne tourne de bout en bout

### 3.1 Frontend sans authentification
Aucune page `/login`, aucun stockage de token, aucun intercepteur axios (`frontend/src/lib/api.ts:5-8`). Toutes les routes backend exigent un JWT. **Chaque appel du frontend renvoie 401**, et comme `isError` n'est lu nulle part, l'UI affiche « Aucune offre / Aucune lettre » — une erreur déguisée en état vide.

### 3.2 Les workers Celery ne peuvent pas exécuter une seule tâche
Quatre cassures indépendantes, chacune suffisante :
1. `workers/tasks/*.py:5` fait `sys.path.insert(0, "../../backend")` → résout vers `/backend`, **inexistant dans l'image** (`workers/Dockerfile:14` ne copie que `./workers`). → `ModuleNotFoundError: app`.
2. `workers/tasks/__init__.py` n'importe aucune tâche, `celery_app.py` n'a ni `include` ni `autodiscover_tasks` → `NotRegistered`.
3. Le worker écoute `--queues=scraping,default` (`workers/Dockerfile:21`) mais le backend envoie lettres et audits sur la queue **`ai`** (`workers_client.py:23,33`) → jamais consommées.
4. Result backend désaligné : backend lit Redis **db 0** (`workers_client.py:4`), workers écrivent en **db 1** (`celery_app.py:6`) → `GET /offres/scan/{id}` et `GET /lettres/generate/{id}` renvoient `PENDING` pour toujours.

Plus : `google-generativeai` absent de `workers/requirements.txt` ; `playwright install` jamais exécuté dans l'image ; `celerybeat-schedule` monté comme répertoire → le conteneur `scheduler` ne démarre pas (`docker-compose.yml:107`, correctif sur la branche `fix/GUI-178`, non mergé).

### 3.3 `NEXT_PUBLIC_API_URL` figé à `localhost:8000` dans l'image de prod
Variable inlinée au build, mais `frontend/Dockerfile` ne déclare aucun `ARG` → les `environment:` des composes sont sans effet. En dev, `docker-compose.yml:67` pointe sur `http://backend:8000`, nom DNS interne non résolvable par le navigateur.

### 3.4 Le déploiement staging lance la stack de dev
`deploy-staging.yml:45` exécute `docker compose up` **sans** `-f infra/docker-compose.staging.yml`. Résultat : backend en `--reload`, port 8000 public, pas de nginx, pas de TLS, pas de certbot. Tout le durcissement de `infra/` est inerte. Le healthcheck final `curl localhost:8000` ne passe *que parce que* la mauvaise config est déployée.

### 3.5 La CI ne s'est jamais exécutée sur `main`
`ci.yml` se déclenche uniquement sur `develop` — branche gelée au 1er commit, 12 commits en retard. Et si elle tournait, 2 jobs sur 3 seraient rouges :
- `docker-compose-validate` : `.env` absent, `POSTGRES_PASSWORD` obligatoire.
- `backend-lint-test` : 14 erreurs `ruff check`, 30/55 fichiers non formatés, `aiosqlite` manquant, et surtout **`tests/conftest.py:35-39` injecte un faux module `app.core`** qui masque le vrai package depuis l'ajout de `app/core/auth.py` → collecte impossible.

**Vérifié en exécutant les tests** (venv propre, shim retiré) : 28 passent, 2 échouent (`202 != 200`, assertions obsolètes dans `test_auth_security.py:108,120`), et `test_routes.py` **bloque indéfiniment** (Celery tente de joindre un broker absent, rien n'est mocké ; ~15 tests n'envoient de plus aucun token et attendent 200 là où le backend renvoie 401).

### 3.6 Bugs applicatifs bloquants dès le 2ᵉ usage
- `workers/tasks/ai.py:38-43` : `scalar_one_or_none()` sans `.limit(1)` → `MultipleResultsFound` dès qu'une entreprise a 2 lettres. La régénération est cassée à partir de la 2ᵉ.
- `workers/tasks/scraping.py:44-55` : dédoublonnage uniquement contre la base, pas dans le lot → deux offres identiques dans un même scan violent la contrainte `unique` et **font perdre tout le lot** de la source.
- `POST /cv/audit` envoie `kwargs={"email_destination": …}` mais la tâche attend `recipient` → absorbé par `**kwargs`, **aucun mail n'est jamais envoyé** depuis l'interface.
- `.env.example:41` : commentaire inline sur `CV_AUDIT_SCHEDULE_CRON` → 7 champs au lieu de 5 → crash du scheduler au démarrage.

---

## 4. Sécurité — le score affiché ne décrit pas `main`

| Rapport | Score | Où il vit |
|---|---|---|
| audit v1 | 1,1/10 | branches uniquement |
| audit v2 | 9,0/10 | **`main`** (seul rapport présent) |
| audit v3 | 7,3/10 | branches uniquement |
| audit v4 | 9,9/10 | branches uniquement |

Les correctifs v3/v4 (GUI-164, GUI-167) **n'ont jamais été fusionnés**. État réel de `main` :

| Finding | Sévérité | Revendiqué | Réel sur `main` |
|---|---|---|---|
| SEC-02 — relais email ouvert sur `/candidatures/{id}/send-email` | HIGH | FIXED | **OUVERT** (`candidatures.py:84-92` : un commentaire, pas de code) |
| SEC-05 — port 8000 exposé | MEDIUM | FIXED | **OUVERT** (`docker-compose.yml:39` + déploiement dev) |
| SEC-06 — rate limit sur scan/audit | MEDIUM | FIXED | **OUVERT** (pas de `core/limiter.py`) ; le rate limit existant est global, pas par IP (pas de `--proxy-headers`) |
| SEC-07 — encodage URL scrapers | MEDIUM | FIXED | **OUVERT** (0 occurrence de `quote`) |
| NEW-01 — `/docs` public en prod | MEDIUM | FIXED | **OUVERT** (`main.py:28-29`) |
| DEP-01→05 — CVE deps (`python-jose 3.3.0`, `lxml 5.3.0`, `aiohttp 3.11.10`…) | 4 MED + 1 LOW | FIXED | **OUVERTS** |
| SEC-10 — hash bcrypt de `"changeme"` en dur | LOW | — | **OUVERT** (`config.py:31`, absent de `.env.example`) |
| Next.js 14.2.18 — GHSA-f82v-jwr5-mffw (bypass auth middleware) | CRITICAL npm | « bloqueur pré-prod » | **OUVERT** (branche GUI-165 non mergée) |
| Renouvellement certbot | — | — | **Cassé** : pas de `location /.well-known/acme-challenge/` dans `nginx.conf`, le `:80` redirige tout → panne TLS à J+90 |
| `client_max_body_size` nginx | — | — | Défaut 1 Mo → **413 sur tout CV > 1 Mo** derrière nginx |

Score effectif recalculé avec le barème des rapports : **≈ 3,6/10**.

---

## 5. Branches — du travail réel est perdu

| Branche | Contenu | Action |
|---|---|---|
| `fix/GUI-167-security-deps` | GUI-164 + GUI-167 réunis : SEC-02/05/06/07/10, NEW-01/03, DEP-01→05 | **Rebaser sur `main`** (⚠️ elle ramènerait `anthropic` et `PyPDF2` — cherry-pick, pas merge naïf) |
| `fix/GUI-178-celerybeat-permissions` | Corrige le montage `celerybeat-schedule` (2 fichiers) | **Cherry-pick immédiat** |
| `claude/server-projects-audit-ddwies` | `docs/backup-rgpd.md` : script `backup.sh`, rétention, checklist RGPD | **Merger tel quel** (0 commit de retard) |
| `frontend/GUI-165-nextjs-upgrade…` | Next 14 → 15.3.3 (CVE). Pas de headers malgré le nom. | Rebaser avant prod (migration `params` async sur 5 pages) |
| `security/GUI-162-audit-v4`, `GUI-166-audit-v3`, `GUI-160-audit-v1` | Rapports v1/v3/v4 | Rapatrier les `.md` dans `main` |
| `develop` | Gelée au 1er commit | Supprimer ou réaligner (la CI dépend d'elle) |
| 10 autres (`GUI-157/158/159/170/172/173`, `feat/ci-demo`, `feat/security-fixes`, `feat/web-app-scaffold`, `security/GUI-160-audit-v2`, `GUI-162-audit-v1`) | Déjà squashées dans `main` ou doublons | Supprimer après extraction des rapports |

---

## 6. Dette et incohérences notables

- **README faux** : promet « Terraform + Ansible + Traefik » ; il n'y a qu'un `provision.sh` de 39 lignes (curl-to-shell Docker, certbot standalone, ufw).
- **Alembic déclaré, jamais initialisé** : ni `alembic.ini` ni `migrations/`. Schéma créé par `create_all`. `deploy-staging.yml:46` fait `alembic upgrade head || true` en silence.
- **Quatre fichiers compose, deux stratégies contradictoires** (racine autonome vs overlays `infra/`). `uploads_data` n'existe que dans le compose local → **en staging les CV disparaissent à chaque redéploiement**.
- **Préfixe `/api`** : seul `scheduler.py` l'utilise ; nginx staging `proxy_pass http://backend;` (sans slash) → 404 sur `/api/offres` (SEC-08, corrigé seulement dans `nginx.local.conf`). Le rewrite de `next.config.js` est mort et faux.
- **Aucun `relationship()` ORM** → N+1 (requête CV par itération dans l'export).
- **Zéro logging** dans tout le backend ; 10 scrapers en `except Exception: pass`.
- **Scheduler configurable = illusion** : `PUT /api/scheduler/cv-audit` écrit en Redis, Beat ne lit que l'env au démarrage.
- **Frontend** : effets de bord dans le `select` React Query (`jobs/page.tsx:45-52`), recherche sans debounce, pas de pagination (max 20 offres visibles), cases à cocher sans action, `generateLettre` et `createCandidature` jamais appelées, carte candidature affichant « Offre #12 » sans titre ni entreprise, PDF via `<a href>` non authentifiable, aucun test.
- IP privée `192.168.1.16` et FQDN `guiguilab.local` codés en dur dans 4 fichiers.
- Deps mortes : `clsx`, `tailwind-merge`, `psycopg2-binary`, `aiohttp`, `tenacity`, `resend`/`reportlab` côté workers ; deps de dev dans l'image prod.
- `email_service.py:28` : expéditeur Resend `noreply@{smtp_user}` → adresse malformée ; `smtp_from` jamais lu.
- `pdf_generator.py:37` : pas d'échappement XML → un `&` dans la lettre casse le PDF.

---

## 7. Feuille de route pour terminer le service

Estimations indicatives en jours-homme, pour un·e dev full-stack connaissant le projet. Chaque phase est livrable et testable indépendamment.

### Phase 0 — Assainir la base (2–3 j)
Objectif : une `main` sur laquelle on peut construire, une CI qui dit la vérité.
- [ ] Cherry-pick `fix/GUI-178` (celerybeat) ; merger `claude/server-projects-audit-ddwies` (doc RGPD).
- [ ] Rebaser `fix/GUI-167-security-deps` en conservant `google-generativeai` + `pypdf` : récupère SEC-02/05/06/07/10, NEW-01/03, DEP-01→05.
- [ ] Rapatrier `audit-v1/v3/v4.md` dans `docs/security/`.
- [ ] `ci.yml` : déclencher sur `main` (+ PR vers `main`) ; supprimer ou réaligner `develop`.
- [ ] Supprimer le shim `tests/conftest.py:21-39` et `/tmp/py_pkgs` ; fusionner les deux `conftest.py` ; ajouter `aiosqlite` ; `pyproject.toml` avec `asyncio_mode`.
- [ ] `test_routes.py` : override `get_current_user`, mocker `send_task` ; corriger les 2 assertions `202` ; retirer les tests documentant des corrections jamais appliquées (ou appliquer les corrections : `Literal` sur `statut`, `SendEmailRequest` sans `candidature_id`).
- [ ] `ruff check --fix` + `ruff format` ; `.env` de CI pour `docker compose config`.
- [ ] README : décrire l'infra réelle, les 3 modes de déploiement, les variables obligatoires.
- [ ] Supprimer les 10 branches obsolètes.

### Phase 1 — Faire tourner la chaîne de bout en bout (4–6 j)
Objectif : login → scan France Travail → offres visibles → lettre générée → email envoyé, en Docker.
- [ ] **Packaging partagé** : contexte de build à la racine, `COPY backend/app` + `COPY workers` dans l'image worker (ou extraire un package `pole_emploi_core` installable). Supprimer les `sys.path.insert`.
- [ ] `celery_app.py` : `include=["tasks.ai","tasks.cv_audit","tasks.scraping"]` ; worker sur `--queues=scraping,ai,default` ; result backend unifié (`CELERY_RESULT_BACKEND` lu des deux côtés via `settings`).
- [ ] `workers/requirements.txt` : ajouter `google-generativeai`, retirer les deps mortes ; `RUN playwright install --with-deps chromium` (ou image `mcr.microsoft.com/playwright/python`).
- [ ] Aligner `email_destination` ↔ `recipient` ; propager l'échec d'envoi (`send_email_with_attachments` retourne `False` en silence).
- [ ] **Frontend auth** : page `/login` (`POST /auth/token` en `x-www-form-urlencoded`), stockage token, intercepteur `Authorization: Bearer`, redirection sur 401, PDF via blob authentifié.
- [ ] `ARG NEXT_PUBLIC_API_URL` dans le stage builder + `build.args` ; `docker-compose.yml:67` → `localhost:8000`. Ou basculer sur un vrai proxy same-origin `/api` (recommandé : supprime le problème de build-time).
- [ ] Décision de préfixe : `APIRouter(prefix="/api")` partout, nginx `proxy_pass http://backend;` cohérent, rewrite Next corrigé.
- [ ] `deploy-staging.yml` : `-f docker-compose.yml -f infra/docker-compose.staging.yml` ; healthcheck via nginx, pas via `:8000`.
- [ ] nginx staging : `location /.well-known/acme-challenge/`, `client_max_body_size 12m`, volume `uploads_data`.
- [ ] `.env.example` complet : `API_USERNAME`, `API_PASSWORD_HASH`, `USER_EMAIL`, `RESEND_API_KEY`, `NEXT_PUBLIC_API_URL`, `CV_AUDIT_SCHEDULE_CRON` sans commentaire inline.
- [ ] Un test d'intégration Docker (compose up → login → scan mocké → 200) dans la CI.

### Phase 2 — Parcours métier utilisable (5–8 j)
Objectif : un·e candidat·e peut réellement s'en servir chaque semaine.
- [ ] **Sources** : garder France Travail (cache du token 25 min, pagination `range`, paramètre `region`, mapping contrats corrigé, `raise_for_status` capturé) + valider **1 ou 2** scrapers réellement fonctionnels (HelloWork ; WTTJ via Algolia). Désactiver les 8 autres plutôt que d'afficher 11 façades. Remplacer `except: pass` par du logging.
- [ ] **UI** : bouton « Générer une lettre » depuis une offre (+ polling), création de candidature depuis une lettre, carte candidature avec titre/entreprise (jointure backend ou `relationship()`), pagination + compteur total, `isError` affiché, `error.tsx`/`loading.tsx`, debounce, effets de bord hors du `select`, composants partagés (Modal, Button).
- [ ] **Alembic réel** : `alembic init`, migration initiale, `create_all` retiré, `alembic upgrade head` effectif au déploiement.
- [ ] **Bugs fonctionnels** : `.limit(1)` dans `ai.py` ; dédoublonnage intra-lot + comptage `imported` ; échappement XML PDF ; `smtp_from` ; `.doc` refusé ou converti ; nom de fichier CV unique ; `relationship()` + N+1.
- [ ] **Scheduler** : soit RedBeat (config Redis réellement lue par Beat) et écran de configuration consommant `/api/scheduler/cv-audit`, soit retirer l'API et l'encart UI. Persister le rapport d'audit CV en base et l'afficher.
- [ ] Logging structuré (JSON) backend + workers ; `SlowAPIMiddleware` réellement installé ; `--proxy-headers` uvicorn.

### Phase 3 — Sécurité et conformité (3–4 j)
Objectif : publiable sur Internet avec des données personnelles.
- [ ] Audit **v5 sur `main`** avec trivy + pip-audit fonctionnel (psycopg2 retiré → `pg_config` inutile).
- [ ] NEW-01 (`docs_url=None` en prod), SEC-10 (refus de démarrer sur hash/secret par défaut), rate limit par IP réel, CSP sans `unsafe-eval`, `python-jose` → `pyjwt`.
- [ ] Next.js 15 (rebaser GUI-165, migrer `params` async) ; ESLint 9 ; headers de sécurité aussi dans `next.config.js`.
- [ ] **RGPD** : endpoint « supprimer toutes mes données » (CV, lettres, candidatures, fichiers), tâche Beat de purge > 24 mois, `infra/backup.sh` + timer systemd, registre des traitements (sous-traitants : France Travail, Google Gemini, SMTP/Resend). Vérifier que l'envoi de CV à Gemini free tier est acceptable (conditions d'utilisation des données).
- [ ] Secrets : `SECRET_KEY`/`API_PASSWORD_HASH` obligatoires (`${VAR:?}`), pas d'IP/FQDN privés dans le dépôt, `ssh-keyscan` remplacé par une `known_hosts` fixe.

### Phase 4 — Qualité et mise en production (3–5 j)
- [ ] Tests frontend (Vitest + Testing Library) sur login, liste, mutation ; E2E Playwright sur le parcours complet.
- [ ] `mypy` bloquant, `requirements-dev.txt` séparé, image prod sans outils de dev, deps mortes retirées.
- [ ] Un seul `docker-compose.yml` + 2 overlays (`local`, `staging`), documentés.
- [ ] Observabilité : healthchecks sur frontend/worker/scheduler/nginx, `depends_on: condition: service_healthy`, alerte sur échec de tâche Celery, rotation des logs.
- [ ] Workflow prod avec label `prod-approved` réellement vérifié, tag d'image, rollback.

**Total : 17 à 26 jours-homme.**

---

## 8. Décisions à prendre avant la Phase 2

1. **Mono ou multi-utilisateur ?** Aujourd'hui un seul compte en config. Le multi-utilisateur impose une table `users`, une inscription, l'isolation des données et change le périmètre RGPD. Recommandation : rester mono-utilisateur pour le MVP, mais poser `user_id` sur les tables dès la migration initiale.
2. **Combien de sources d'offres ?** 11 façades dont 10 mortes coûtent plus qu'elles ne rapportent. Recommandation : France Travail + HelloWork, extensible ensuite.
3. **Scheduler piloté par l'UI ou par l'env ?** RedBeat = 1 jour de plus ; env = supprimer 2 endpoints et un encart. Recommandation : env pour le MVP.
4. **Gemini free tier avec des CV réels ?** Question de conformité (données personnelles envoyées à un sous-traitant hors UE, conditions du tier gratuit). À trancher avant d'ouvrir le service à d'autres personnes que l'auteur.
5. **Préfixe `/api` partout** — à décider en Phase 1, ça conditionne nginx, Next et les tests.

---

*Rapport produit à partir de l'analyse du code et de l'exécution des tests ; aucune modification fonctionnelle n'a été apportée au projet dans ce commit.*
