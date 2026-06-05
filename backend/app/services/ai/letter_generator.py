import json
import httpx
from app.config import settings


def _ollama_chat(system_prompt: str, user_prompt: str, expect_json: bool = False) -> str:
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        **({"format": "json"} if expect_json else {}),
    }
    try:
        resp = httpx.post(
            f"{settings.ollama_host}/api/chat",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except httpx.ConnectError:
        raise RuntimeError(
            f"Ollama est inaccessible ({settings.ollama_host}). "
            "Vérifiez que le service Ollama est démarré et que OLLAMA_HOST est correct."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Erreur Ollama HTTP {e.response.status_code}: {e.response.text[:200]}")


def generate_cover_letter(
    cv_text: str,
    offre_titre: str,
    offre_entreprise: str,
    offre_description: str,
    type_contrat: str | None = None,
) -> str:
    contract_hint = "en alternance" if type_contrat and "alternance" in type_contrat.lower() else "en CDI/CDD"

    system_prompt = f"""Tu es un expert en rédaction de lettres de motivation pour le secteur tech/informatique en France.
Tu rédiges des lettres professionnelles, personnalisées, convaincantes et adaptées au ton de l'entreprise.
Voici le CV du candidat (utilise ces informations comme base pour personnaliser la lettre) :

<cv>
{cv_text}
</cv>"""

    user_prompt = f"""Rédige une lettre de motivation {contract_hint} pour le poste suivant :

**Poste** : {offre_titre}
**Entreprise** : {offre_entreprise}
**Description** :
{offre_description[:3000]}

Règles :
- Ton professionnel adapté au secteur tech
- Maximum 400 mots
- Structure : accroche percutante / compétences clés alignées au poste / motivation pour l'entreprise / call to action
- Pas de formules génériques ou de clichés
- Utilise le prénom et les compétences du CV pour personnaliser
- Termine avec une formule de politesse adaptée au type de contrat

Retourne uniquement le texte de la lettre, sans balises ni méta-commentaires."""

    return _ollama_chat(system_prompt, user_prompt)


def generate_cv_audit(cv_text: str, offres_recentes: list[str] | None = None) -> dict:
    offres_context = "\n".join(offres_recentes[:10]) if offres_recentes else "Pas d'offres récentes disponibles."

    system_prompt = """Tu es un expert RH et conseiller en carrière tech en France.
Tu analyses des CV pour le secteur Informatique / Dev / Data / Alternance tech.
Ton analyse est structurée, bienveillante mais honnête, axée sur l'employabilité.
Réponds uniquement avec un objet JSON valide, sans texte supplémentaire."""

    user_prompt = f"""Analyse ce CV en détail :

<cv>
{cv_text}
</cv>

Offres d'emploi récentes dans le secteur (pour identifier les compétences en demande) :
<offres_recentes>
{offres_context}
</offres_recentes>

Fournis ton analyse au format JSON strict avec ces champs :
{{
  "points_forts": ["..."],
  "axes_amelioration": ["..."],
  "recommandations": ["..."],
  "score_global": <entier entre 0 et 10>,
  "competences_manquantes": ["..."],
  "resume_executif": "..."
}}"""

    text = _ollama_chat(system_prompt, user_prompt, expect_json=True)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return {
        "points_forts": [],
        "axes_amelioration": [],
        "recommandations": [text],
        "score_global": None,
        "competences_manquantes": [],
        "resume_executif": text[:300],
    }
