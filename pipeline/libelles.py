"""Libellés d'affichage respectueux des personnes.

Les nomenclatures officielles (FINESS, secteurs RPPS, Assurance Maladie) contiennent des formulations
datées ou stigmatisantes. Les données brutes et intermédiaires gardent le libellé d'origine, pour la
traçabilité et les appariements. Tout ce qu'un lecteur voit passe par la table libelles.csv, validée
par Lucas, qui associe chaque libellé d'origine à un libellé d'affichage. Les sigles d'usage
(EHPAD, IME, CMP...) restent toujours visibles pour que les structures soient identifiables."""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from .util import norm

TABLE = Path(__file__).with_name("libelles.csv")

# Termes à proscrire dans tout ce qu'un lecteur voit. Motifs appliqués au texte normalisé
# (minuscules, sans accents, ponctuation réduite à des espaces).
TERMES_PROSCRITS = [
    (r"\bhandicape(e)?s?\b", "handicapé(e)s, préférer « personnes en situation de handicap »"),
    (r"\bpolyhandicape(e)?s\b", "polyhandicapé(e)s, préférer « en situation de polyhandicap »"),
    (r"\bmalad(es|ies) mentales?\b|\bmalades? mentaux\b", "malades mentaux, maladies mentales"),
    (r"\bdeficients?\b|\bdeficientes?\b", "déficient(s), préférer une formulation centrée sur la personne"),
    (r"\bdeficience mentale\b", "déficience mentale, préférer « déficience intellectuelle »"),
    (r"\btoxicomanes?\b", "toxicomane(s), préférer « personnes ayant une addiction »"),
    (r"\balcooliques\b", "alcooliques, préférer « personnes ayant une addiction à l'alcool »"),
    # diagnostic employé comme nom (« les dépressifs »), l'adjectif (« épisodes dépressifs ») reste permis
    (r"\b(les|des|aux|ces) (schizophrenes|depressifs|bipolaires|psychotiques|autistes|anorexiques)\b",
     "diagnostic substantivé, préférer « personnes vivant avec... »"),
    (r"\binadapte(e)?s?\b", "inadapté(e)s"),
    (r"\bgrabataires?\b", "grabataire(s)"),
    (r"\bagees dependantes\b", "personnes âgées dépendantes, préférer « en perte d'autonomie »"),
    (r"\bdebiles?\b|\barrieres? mentaux\b|\balienes\b|\binfirmes\b", "terme péjoratif ou daté"),
]
# Vocabulaire à éviter sur le site et dans les rapports (consigne de Lucas du 4 octobre 2026), pour ne pas
# présenter les contenus comme « automatiques » ou « générés ». Vérifié avec les termes à proscrire.
VOCABULAIRE_A_EVITER = [
    (r"\bautomatique(s|ment)?\b", "vocabulaire « automatique » à éviter sur le site"),
    (r"\bgenere(e|s|es)? automatiquement\b|\bproduit automatiquement\b", "vocabulaire « généré » à éviter sur le site"),
    # consigne du 4 octobre 2026, ne pas mettre en avant l'outil qui télécharge ou calcule
    (r"\b(le|du|par le|au) programme\b", "« le programme » mis en avant, préférer une formulation centrée sur les données"),
]

# Noms propres d'institutions conservés tels quels (validé par Lucas pour la MDPH).
EXCEPTIONS = [r"maisons? departementales? des personnes handicapees"]


@lru_cache(maxsize=1)
def table() -> list[dict]:
    with open(TABLE, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


@lru_cache(maxsize=1)
def _index() -> dict:
    out = {}
    for r in table():
        out[(r["source"], r["code"])] = r["libelle_affichage"]
        out[("*", norm(r["libelle_origine"]))] = r["libelle_affichage"]
    return out


def affichage(libelle: str, source: str = "", code: str = "") -> str:
    """Libellé d'affichage. Cherche d'abord par source et code, puis par libellé d'origine
    (comparaison normalisée). Un libellé absent de la table est renvoyé tel quel."""
    if libelle is None:
        return libelle
    i = _index()
    if source and code and (source, str(code)) in i:
        return i[(source, str(code))]
    return i.get(("*", norm(libelle)), libelle)


def termes_proscrits(texte: str) -> list[str]:
    """Liste des termes à proscrire présents dans un texte (vide si le texte est conforme)."""
    t = norm(re.sub(r"https?://\S+", " ", texte))   # les adresses web ne sont pas du texte lu
    for e in EXCEPTIONS:
        t = re.sub(e, " ", t)
    trouves = []
    for motif, explication in TERMES_PROSCRITS + VOCABULAIRE_A_EVITER:
        for m in re.finditer(motif, t):
            debut = max(m.start() - 40, 0)
            trouves.append(f"{explication} … {t[debut:m.end() + 40].strip()} …")
    return trouves
