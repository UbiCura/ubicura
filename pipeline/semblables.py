"""Territoires semblables : une seule définition pour tout le site (structure validée le 26 novembre 2026,
prototypes/structure_2026-11-25/notes.md, section 4).

Sept mesures de l'INSEE, jamais l'offre de soins : densité de population (en logarithme), parts des moins de 15 ans, des
65-79 ans et des 80 ans et plus, niveau de vie médian, taux de pauvreté et taux de chômage. Chacune est ramenée à sa
dispersion entre les territoires du niveau (écart à la moyenne divisé par l'écart type), puis la distance euclidienne
désigne les cinq territoires les plus proches, du même niveau, hors outre-mer. Un territoire d'outre-mer, ou à qui manque
une des sept mesures, n'a pas de semblables et n'en est le semblable d'aucun autre.

Calculé ici seulement. Lu par les rapports et la fiche de département (rapport_territoire.semblables), et par Comparer
(pipeline/atelier.py, A.semb). C'est une comparaison avec des territoires de profil proche, pas une mesure du besoin.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config

MESURES = ["densite_pop", "part_0_14", "part_65_79", "part_80p", "revenu_median", "taux_pauvrete", "taux_chomage"]
NOMBRE = 5
NIVEAUX = ("dep", "epci")
# le critère en clair, écrit tel quel par Comparer et repris par la fiche
CRITERE = ("Choisis sur sept mesures de l'INSEE, les mêmes que pour les départements de profil semblable des fiches : "
           "densité de population (en logarithme), parts des moins de 15 ans, des 65-79 ans et des 80 ans et plus, "
           "niveau de vie médian, taux de pauvreté et taux de chômage, chacune ramenée à sa dispersion. Ce sont les cinq "
           "{niveaux} les plus proches sur ces sept mesures, hors outre-mer. Ce ne sont pas des voisins, et ce n'est pas "
           "une mesure du besoin.")
NIV_PLURIEL = {"dep": "départements", "epci": "intercommunalités"}


def critere(niveau: str) -> str:
    return CRITERE.format(niveaux=NIV_PLURIEL[niveau])


def semblables(ctx: pd.DataFrame | None, outre_mer=(), k: int = NOMBRE) -> dict:
    """Pour chaque territoire de ctx (indexé par code, une colonne par mesure), les k territoires les plus proches, dans
    l'ordre de la distance. outre_mer, les codes écartés (ni semblables, ni semblables d'un autre)."""
    if ctx is None or not len(ctx):
        return {}
    cols = [c for c in MESURES if c in ctx]
    x = ctx.loc[~ctx.index.isin(set(outre_mer)), cols].apply(pd.to_numeric, errors="coerce").astype(float).copy()
    if "densite_pop" in x:
        x["densite_pop"] = np.log(x["densite_pop"].clip(lower=1))
    x = x.dropna()
    if len(x) <= k:
        return {}
    z = (x - x.mean()) / x.std(ddof=0)
    a = z.to_numpy()
    d = np.sqrt(((a[:, None, :] - a[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    return {c: [x.index[j] for j in np.argsort(d[i], kind="stable")[:k]] for i, c in enumerate(x.index)}


def lire_contexte(dernier: Path, niveau: str) -> pd.DataFrame | None:
    """Les sept mesures d'un niveau, lues dans contexte_<niveau>.csv du dossier de résultats."""
    f = Path(dernier) / f"contexte_{niveau}.csv"
    if not f.exists():
        return None
    x = pd.read_csv(f, sep=";", decimal=",", dtype={"code": str}, encoding="utf-8-sig")
    if "code" not in x:
        return None
    return x.set_index("code")[[c for c in MESURES if c in x]]


def outre_mer(niveau: str, parents: dict | None = None) -> set:
    """Codes d'outre-mer d'un niveau. Pour les intercommunalités, parents donne le département de chacune."""
    drom = set(config.DEPS_DROM)
    if niveau == "dep":
        return drom
    return {c for c, p in (parents or {}).items() if p in drom}


def par_niveau(dernier: Path, niveau: str, parents: dict | None = None) -> dict:
    """Semblables d'un niveau depuis le dossier de résultats (parents, département de chaque intercommunalité)."""
    if niveau == "epci" and not parents:
        return {}
    return semblables(lire_contexte(dernier, niveau), outre_mer(niveau, parents))


def depuis_site(sd: dict, dernier: Path) -> dict:
    """Semblables des départements et des intercommunalités, pour Comparer : {niveau: {code: [codes]}}."""
    parents = {u["c"]: u.get("p") for u in sd["niveaux"]["epci"]["units"]}
    return {lv: par_niveau(dernier, lv, parents if lv == "epci" else None) for lv in NIVEAUX}
