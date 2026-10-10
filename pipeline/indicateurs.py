"""Liste combinée des indicateurs de contexte, ceux de l'INSEE (config.CONTEXTE) et ceux des bases
complémentaires (Assurance Maladie, descripteurs de complements/), avec libellé, unité, explication,
source, famille et licence. Le site, le rapport et le dictionnaire des colonnes s'appuient sur elle."""
from __future__ import annotations

from . import config
from .lecture import EXPLICATIONS_CONTEXTE

NIVEAUX = {"com": "communes", "epci": "intercommunalités", "dep": "départements", "reg": "régions"}
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
    # niveaux où l'indicateur est réellement publié (au moins une valeur), pour le dictionnaire et la page méthode
    tables = (contexte or {}).get("contexte", {}) if contexte else {}
    for d in tout:
        d["niveaux"] = [NIVEAUX[n] for n in ("com", "epci", "dep", "reg")
                        if n in tables and d["id"] in tables[n] and tables[n][d["id"]].notna().any()]
    return tout


def libelles(contexte: dict | None) -> dict:
    return {d["id"]: d["label"] for d in liste(contexte)}


def odbl(contexte: dict | None) -> set:
    """Identifiants des indicateurs sous licence ODbL, à isoler dans des fichiers à part."""
    return {d["id"] for d in liste(contexte) if "odbl" in d["licence"].lower()}
