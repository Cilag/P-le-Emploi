# Pôle Emploi — Assistant de Candidature

Assistant web intelligent pour automatiser et optimiser les candidatures sur France Travail.

## Stack

| Couche | Technologie |
|--------|-------------|
| Backend API | FastAPI (Python 3.12) |
| Frontend | Next.js 14 (React/TypeScript) |
| Base de données | PostgreSQL 16 |
| Cache / Queue | Redis 7 |
| Worker scraping | Celery |
| Scheduler CV | Celery Beat |

## Démarrage rapide

```bash
cp .env.example .env
# Renseignez les variables dans .env
docker compose up --build
```

L'application sera disponible sur :
- Frontend : http://localhost:3000
- Backend API : http://localhost:8000
- Docs API : http://localhost:8000/docs

## Structure du projet

```
├── backend/      # FastAPI — API REST + logique métier
├── frontend/     # Next.js — interface utilisateur
├── workers/      # Celery workers (scraping + scheduler CV)
├── infra/        # Terraform + Ansible + configs Nginx/Traefik
└── .github/
    └── workflows/
        ├── ci.yml            # Lint + tests sur push/PR → develop
        └── deploy-staging.yml # Déploiement auto sur merge → main
```

## Branches

| Branche | Rôle |
|---------|------|
| `main` | Déploiement staging automatique |
| `develop` | Intégration continue (CI) |

> **Production** : uniquement via PR labelée `prod-approved`.

## Variables d'environnement

Voir `.env.example` pour la liste complète.

## CI/CD

- Push / PR vers `develop` → lint + tests + build
- Merge dans `main` → déploiement automatique staging
- Les secrets sont gérés via GitHub Secrets (jamais en clair)
