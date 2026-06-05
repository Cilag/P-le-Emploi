import anthropic
from app.config import settings


_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def generate_cover_letter(
    cv_text: str,
    offre_titre: str,
    offre_entreprise: str,
    offre_description: str,
    type_contrat: str | None = None,
) -> str:
    client = get_client()
    contract_hint = "en alternance" if type_contrat and "alternance" in type_contrat.lower() else "en CDI/CDD"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=[
            {
                "type": "text",
                "text": f"""Tu es un expert en rédaction de lettres de motivation pour le secteur tech/informatique en France.
Tu rédiges des lettres professionnelles, personnalisées, convaincantes et adaptées au ton de l'entreprise.
Voici le CV du candidat (utilise ces informations comme base pour personnaliser la lettre) :

<cv>
{cv_text}
</cv>""",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""Rédige une lettre de motivation {contract_hint} pour le poste suivant :

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

Retourne uniquement le texte de la lettre, sans balises ni méta-commentaires.""",
            }
        ],
    )

    return response.content[0].text


def generate_cv_audit(cv_text: str, offres_recentes: list[str] | None = None) -> dict:
    client = get_client()
    offres_context = "\n".join(offres_recentes[:10]) if offres_recentes else "Pas d'offres récentes disponibles."

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": """Tu es un expert RH et conseiller en carrière tech en France.
Tu analyses des CV pour le secteur Informatique / Dev / Data / Alternance tech.
Ton analyse est structurée, bienveillante mais honnête, axée sur l'employabilité.""",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""Analyse ce CV en détail :

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
}}""",
            }
        ],
    )

    import json
    text = response.content[0].text
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
