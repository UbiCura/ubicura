"""Thèmes transversaux du site (décision de Lucas du 8 novembre 2026, navigation, étape 2). Un thème réunit, autour d'une
même question, des indicateurs de plusieurs domaines : la santé mentale (sa page existe, domaine/sante-mentale.html),
l'addictologie, la géographie sociale, le grand âge, et la victimologie quand ses bases seront intégrées.

Les étiquettes sont écrites indicateur par indicateur dans `pipeline/themes_indicateurs.csv` (id;libelle;themes;sensible),
lu ici et versé au catalogue unique (affichage.catalogue). Toute base ajoutée y inscrit ses indicateurs (liste à cocher
de docs/nouvelle_base.md, étape 9 quater) ; un test échoue si un indicateur du catalogue n'y figure pas. La marque
« sensible » (délinquance, violences) écarte un indicateur de toute proposition d'office avec la santé mentale (décision
de Lucas du 31 octobre 2026) ; il reste dans le croisement libre."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

FICHIER = Path(__file__).with_name("themes_indicateurs.csv")

# questions des pages santé mentale et santé reprises sur la page du thème, avec leur figure et leur « Comment lire »
# (mêmes textes, mêmes figures que les pages de l'offre, pages_domaine.QUESTIONS) : (famille, intertitre du rapport)
THEMES = [
    {"id": "sante_mentale", "nom": "Santé mentale", "page": "domaine/sante-mentale.html"},
    {"id": "addictologie", "nom": "Addictologie",
     "chapeau": "L’offre de soins en addictologie, les consommations et le recours aux soins qui s’y rapportent, et "
                "ce qui les entoure. Les consommations ne sont publiées que par région.",
     "questions": [("sm", "Consommations d'alcool et de tabac, par région", "De l’offre aux consommations en addictologie")],
     "explorer": [("explorer.html#qAddicto", "De l’offre aux consommations en addictologie")]},
    {"id": "geographie_sociale", "nom": "Géographie sociale",
     "chapeau": "Le niveau de vie, l’emploi, la formation, le logement et les familles des habitants, et la façon dont "
                "l’offre de soins se répartit selon eux.",
     "questions": [("sm", "Offre selon le niveau de vie des territoires", "L’offre de santé mentale suit-elle le niveau de vie des habitants ?"),
                   ("sante", "Offre selon le niveau de vie des territoires", "L’offre de santé suit-elle le niveau de vie des habitants ?")],
     "explorer": [("explorer.html#qInegalites", "Les territoires modestes sont-ils moins bien dotés ?"),
                  ("explorer.html#trajectoires", "Les départements modestes rattrapent-ils leur retard depuis 2016 ?")]},
    {"id": "grand_age", "nom": "Grand âge",
     "chapeau": "Les habitants de 65 ans et plus, ceux qui vivent seuls, les EHPAD, les gériatres et les maladies qui "
                "touchent surtout le grand âge.",
     "questions": [], "explorer": []},
    {"id": "victimologie", "nom": "Victimologie", "a_venir": True},
]
PAR_ID = {t["id"]: t for t in THEMES}


def slug(tid: str) -> str:
    return tid.replace("_", "-")


@lru_cache(maxsize=1)
def etiquettes() -> dict[str, dict]:
    """Thèmes et marque sensible de chaque indicateur, par identifiant du catalogue."""
    out = {}
    with FICHIER.open(encoding="utf-8-sig", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            out[l["id"]] = {"themes": [t for t in (l.get("themes") or "").split() if t],
                            "sensible": (l.get("sensible") or "").strip().lower() in ("oui", "1", "vrai")}
    return out


def cle(ident: str) -> str:
    """Identifiant d'une ligne du fichier : « prof:psychiatre » pour « prof:psychiatre:all »."""
    return ":".join(ident.split(":")[:2]) if ident.startswith("prof:") else ident


def themes_de(ident: str) -> list[str]:
    return (etiquettes().get(cle(ident)) or {}).get("themes", [])


def sensible(ident: str) -> bool:
    return (etiquettes().get(cle(ident)) or {}).get("sensible", False)


def controler(ids: list[str]) -> list[str]:
    """Défauts des étiquettes : indicateur du catalogue sans ligne, ligne sans indicateur, thème inconnu, indicateur
    sensible marqué santé mentale."""
    e = etiquettes()
    ids = {cle(i) for i in ids}
    pb = [f"{i} : absent de themes_indicateurs.csv" for i in sorted(ids) if i not in e]
    pb += [f"{i} : ligne de themes_indicateurs.csv sans indicateur au catalogue" for i in e if i not in ids]
    for i, x in e.items():
        pb += [f"{i} : thème inconnu « {t} »" for t in x["themes"] if t not in PAR_ID or PAR_ID[t].get("a_venir")]
        if x["sensible"] and "sante_mentale" in x["themes"]:
            pb.append(f"{i} : indicateur sensible proposé d'office avec la santé mentale")
    return pb
