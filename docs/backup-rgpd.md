# Sauvegarde & RGPD — Pôle Emploi

**Objet :** combler le seul angle mort non couvert par [`docs/security/audit-v2.md`](security/audit-v2.md)
(9,0/10) — la **sauvegarde de la base** et la **rétention des données personnelles**.

L'application manipule des **données à caractère personnel** (profils candidats, CV uploadés,
lettres de motivation, historique de candidatures). Elle entre donc dans le champ du **RGPD** :
sécurité *et* sauvegarde *et* minimisation/rétention.

---

## 1. Où tourne l'application (3 modes de déploiement existants)

| Mode | Fichier | Usage | Exposition |
|---|---|---|---|
| **Dev** | `docker-compose.yml` | développement local (hot-reload, `target: dev`) | ports 3000/8000 en clair |
| **Local (.16)** | `docker-compose.local.yml` | déploiement autonome sur le serveur MSI, HTTP via nginx `:8080` | pensé pour `pole-emploi.guiguilab.local` / `192.168.1.16` |
| **Staging (VPS)** | `docker-compose.yml` + `infra/docker-compose.staging.yml` | VPS public, nginx + TLS certbot (80/443) | backend `8000` **non exposé** (SEC-05) |

> **À trancher (audit serveur) :** si le mode **local (.16)** est réellement utilisé, l'application
> doit être **ajoutée à l'inventaire `servermsi`** et à sa **politique de sauvegarde**, au même titre
> que Paperclip et bot-polymarket.

---

## 2. Données à sauvegarder

| Élément | Support | Contenu sensible |
|---|---|---|
| Base PostgreSQL (`db_data`) | volume Docker | offres, candidatures, CV parsés, lettres, comptes — **PII** |
| CV uploadés (`uploads_data`) | volume Docker | fichiers PDF/DOCX candidats — **PII** |
| Redis (`redis_data`) | volume Docker | file Celery / cache (non critique, reconstructible) |

---

## 3. Script de sauvegarde (pg_dump + uploads)

```bash
#!/usr/bin/env bash
# infra/backup.sh — dump PostgreSQL + archive des CV, chiffré hors site (restic).
set -euo pipefail

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="/tmp/pole-emploi-backup-$STAMP"
mkdir -p "$OUT"

# 1. Dump base (nom du conteneur selon le mode : *-db-1)
docker exec "$(docker ps -qf name=db)" \
  pg_dump -U "${POSTGRES_USER:-pole_emploi}" "${POSTGRES_DB:-pole_emploi_db}" \
  > "$OUT/pole-emploi-db.sql"

# 2. Archive des CV uploadés
docker run --rm -v pole-emploi_uploads_data:/data -v "$OUT":/backup alpine \
  tar czf /backup/uploads.tgz -C /data .

# 3. Envoi chiffré hors site (réutilise la conf restic de servermsi/backup.md)
set -a; source ~/.restic-env; set +a
restic backup "$OUT" --tag pole-emploi
rm -rf "$OUT"

# 4. Rétention
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 3 --prune
```

Planifier via un **timer systemd** (cf. modèle dans `servermsi/docs/backup.md`) — quotidien, 23h30.

> ⚠️ **Une sauvegarde non testée n'existe pas.** Vérifier une restauration complète une fois/mois :
> recharger `pole-emploi-db.sql` dans une base jetable et contrôler l'intégrité.

---

## 4. Checklist RGPD

- [ ] **Base de légalité** documentée (consentement de l'utilisateur du service).
- [ ] **Minimisation** : ne stocker que les données nécessaires à la candidature.
- [ ] **Rétention** : purge automatique des candidatures/CV inactifs (ex. > 24 mois) — tâche Celery Beat dédiée.
- [ ] **Droit à l'effacement** : endpoint/procédure de suppression totale d'un compte + ses CV + ses candidatures.
- [ ] **Chiffrement au repos** des sauvegardes (restic ✅) et **en transit** (TLS staging ✅ ; à ajouter en mode local).
- [ ] **Journalisation des accès** aux données personnelles (a minima logs nginx + API auth).
- [ ] **Registre des traitements** (obligation RGPD si traitement régulier).
- [ ] **Sous-traitants** : France Travail API, Google Gemini (LLM), SMTP — vérifier qu'aucune PII non nécessaire ne leur est transmise.

---

## 5. Lien avec l'audit serveur

Ce document répond à l'axe **« Trancher & normaliser P-le-Emploi »** de
`servermsi/docs/audit-serveur-projets.md`. Les correctifs applicatifs de sécurité (JWT, headers,
rate-limiting, TLS) sont déjà traités et validés dans [`docs/security/audit-v2.md`](security/audit-v2.md)
(9,0/10). Le présent fichier ne couvre que **sauvegarde + RGPD**, seul volet restant.
