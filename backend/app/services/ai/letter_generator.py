import json

from app.services.ai.llm import chat

CV_MAX = 6000
DESCRIPTION_MAX = 5000


def nettoyer_reponse(texte: str) -> str:
    """Retire un éventuel bloc ```…``` autour de la lettre."""
    t = texte.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rstrip()
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


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
{cv_text[:CV_MAX]}
</cv>"""

    user_prompt = f"""Rédige une lettre de motivation {contract_hint} pour le poste suivant :

**Poste** : {offre_titre}
**Entreprise** : {offre_entreprise}
**Description** :
{offre_description[:DESCRIPTION_MAX]}

Règles :
- Ton professionnel adapté au secteur tech
- Maximum 400 mots
- Structure : accroche percutante / compétences clés alignées au poste / motivation pour l'entreprise / call to action
- Pas de formules génériques ou de clichés
- Utilise le prénom et les compétences du CV pour personnaliser
- Termine avec une formule de politesse adaptée au type de contrat
- Réponds uniquement par le texte de la lettre, sans préambule ni bloc de code

Retourne uniquement le texte de la lettre, sans balises ni méta-commentaires."""

    return nettoyer_reponse(chat(system_prompt, user_prompt))


def generate_cv_audit(cv_text: str, offres_recentes: list[str] | None = None) -> dict:
    offres_context = "\n".join(offres_recentes[:10]) if offres_recentes else "Pas d'offres récentes disponibles."

    system_prompt = """Tu es un expert RH et conseiller en carrière tech en France.
Tu analyses des CV pour le secteur Informatique / Dev / Data / Alternance tech.
Ton analyse est structurée, bienveillante mais honnête, axée sur l'employabilité.
Réponds uniquement avec un objet JSON valide, sans texte supplémentaire."""

    user_prompt = f"""Analyse ce CV en détail :

<cv>
{cv_text[:CV_MAX]}
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

    text = chat(system_prompt, user_prompt)
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
