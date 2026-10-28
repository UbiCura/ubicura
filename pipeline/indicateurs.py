"""Liste combinée des indicateurs de contexte, ceux de l'INSEE (config.CONTEXTE) et ceux des bases
complémentaires (Assurance Maladie, descripteurs de complements/), avec libellé, unité, explication,
source, famille et licence. Le site, le rapport et le dictionnaire des colonnes s'appuient sur elle.

Catalogue unique (décision de Lucas du 28 octobre 2026) : le site, l'Explorer et l'API lisent cette liste. Chaque
indicateur porte aussi l'identifiant de sa licence dans le registre (pipeline/licences.py), ses niveaux en codes, le type
de sa valeur, sa règle d'agrégation pour une zone faite de plusieurs territoires et la page de sa source."""
from __future__ import annotations

import re

from . import config, licences
from .lecture import EXPLICATIONS_CONTEXTE

NIVEAUX = {"com": "communes", "epci": "intercommunalités", "dep": "départements", "reg": "régions"}

# Règle d'agrégation d'un indicateur pour une zone faite de plusieurs territoires, d'après son unité (première règle qui
# s'applique). Une moyenne pondérée par la population n'est exacte que pour un taux rapporté à toute la population, elle
# est seulement approchée pour une part dont le dénominateur est une sous-population (actifs, ménages, 15 ans et plus).
# Une médiane, un taux standardisé sur l'âge, une distance médiane, une densité ou un taux rapporté à une sous-population
# que nous n'avons pas par territoire ne s'agrègent pas.
AGREGATION = [
    (r"standardis", "non_agregeable", "taux standardisé"),
    (r"^km$", "non_agregeable", "distance médiane"),
    (r"hab\./km", "non_agregeable", "densité"),
    (r"^€$", "non_agregeable", "montant médian ou moyen"),
    (r"moins de|ans et plus|élèves|passages|0-20 ans|adultes", "non_agregeable", "taux rapporté à une sous-population"),
    (r"pour 1[0 ]*000 hab|pour 100 000 hab|pour 1 000 habitants|pour 100 000 habitants", "moyenne_ponderee_population", "taux"),
    (r"^%$", "moyenne_ponderee_population_approchee", "part"),
]


def agregation(unite: str) -> tuple[str, str]:
    """Règle d'agrégation et type de valeur d'un indicateur, d'après son unité."""
    u = (unite or "").strip()
    return next(((regle, type_valeur) for motif, regle, type_valeur in AGREGATION if re.search(motif, u)),
                ("non_agregeable", "autre"))


def page_source(source: str) -> str:
    """Page de présentation du jeu de données, d'après config.SOURCES_INFO (motif sur le nom de la source)."""
    for motif, _, _, page in config.SOURCES_INFO:
        if page and re.search(motif, source or ""):
            return page
    return ""
SOURCE_INSEE = "INSEE, dossier complet (recensement de la population, Filosofi)"


def liste(contexte: dict | None) -> list[dict]:
    base = [{"id": c[0], "label": c[1], "unite": c[2], "explication": EXPLICATIONS_CONTEXTE.get(c[0], ""),
             "source": SOURCE_INSEE, "famille": "", "licence": "Licence Ouverte 2.0", "base": True,
             "groupe": "Profil de la population"}
            for c in config.CONTEXTE]
    presents = set().union(*[set(t.columns) for t in (contexte or {}).get("contexte", {}).values()]) \
        if contexte and contexte.get("contexte") else set()
    vuln = [{"id": c[0], "label": c[1], "unite": c[2], "explication": EXPLICATIONS_CONTEXTE.get(c[0], ""),
             "source": SOURCE_INSEE, "famille": "", "licence": "Licence Ouverte 2.0", "base": False,
             "groupe": config.GROUPE_VULNERABILITE}
            for c in config.CONTEXTE_VULNERABILITE if c[0] in presents]
    autres =[{"id": d["id"], "label": d["libelle"], "unite": d.get("unite", ""), "explication": d.get("explication", ""),
               "source": d.get("source", ""), "famille": d.get("famille", ""), "licence": d.get("licence", ""),
               "base": False, "groupe": d.get("groupe") or ("Santé mentale, besoins et recours aux soins"
                                                           if d.get("famille") else "Autres indicateurs")}
              for d in (contexte or {}).get("indicateurs", [])]
    tout = base + vuln + autres
    # licence du registre (libellé affiché tiré du registre), règle d'agrégation, page de la source
    for d in tout:
        d["licence_id"] = licences.identifiant(d["licence"], d["source"])
        d["licence"] = licences.affiche(d["licence_id"]) or d["licence"]
        d["agregation"], d["type_valeur"] = agregation(d["unite"])
        d["page_source"] = page_source(d["source"])
    # niveaux où l'indicateur est réellement publié (au moins une valeur), pour le dictionnaire et la page méthode
    tables = (contexte or {}).get("contexte", {}) if contexte else {}
    for d in tout:
        d["niveaux_codes"] = [n for n in ("com", "epci", "dep", "reg")
                              if n in tables and d["id"] in tables[n] and tables[n][d["id"]].notna().any()]
        d["niveaux"] = [NIVEAUX[n] for n in d["niveaux_codes"]]
    return tout


def libelles(contexte: dict | None) -> dict:
    return {d["id"]: d["label"] for d in liste(contexte)}


def odbl(contexte: dict | None) -> set:
    """Identifiants des indicateurs sous licence ODbL, à isoler dans des fichiers à part."""
    return {d["id"] for d in liste(contexte) if d["licence_id"] == "odbl-1.0"}
