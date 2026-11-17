"""Verdicts de la vérification à la main des structures autres que les CMP (contenus/verdicts_structures.csv).

Les CMP ont leur fichier et leurs règles (pipeline/verdicts.py). Pour les autres types (urgences, maternités, dialyse,
réadaptation...), un verdict retire une inscription des bases qui ne correspond pas à un lieu de soins distinct :
- doublon : la même structure, inscrite deux fois (sous un hôpital et sous le groupement qui gère son service, sous
  l'ancien et le nouveau numéro d'un site) ;
- ferme, introuvable : la structure n'existe plus, ou aucune source ne la connaît.
Exception du 15 novembre 2026 (règles du projet, partie 4) : un verdict porte sur une structure, avec une
source officielle datée et cliquable, expire au bout d'un an, et ne change jamais un chiffre calculé autrement qu'en
retirant l'inscription qu'il désigne. Un verdict sans source, périmé ou dont la structure n'est pas trouvée est écarté
et consigné.

Colonnes : type;cle;etablissement;structure;verdict;commentaire;date. La clé est celle des verdicts des CMP
(verdicts.cle : entité juridique, numéro FINESS, nom de la commune, début du nom simplifié).
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import config
from .util import JOURNAL

FICHIER = config.RACINE / "contenus" / "verdicts_structures.csv"
COLS = ["type", "cle", "etablissement", "structure", "verdict", "commentaire", "date"]
SORTES = {"doublon": "doublon d'une autre structure", "ferme": "fermée",
          "introuvable": "introuvable sur toutes les sources"}
DUREE_JOURS = 365


def charger() -> pd.DataFrame:
    if not FICHIER.exists():
        return pd.DataFrame(columns=COLS)
    v = pd.read_csv(FICHIER, sep=";", dtype=str, encoding="utf-8").fillna("")
    return v.drop_duplicates(["type", "cle"], keep="last").reindex(columns=COLS, fill_value="")


def valable(r, aujourd: dt.date | None = None) -> str:
    """Raison pour laquelle un verdict est écarté, vide s'il est valable."""
    aujourd = aujourd or dt.date.today()
    if r["verdict"] not in SORTES:
        return "verdict inconnu"
    if not re.search(r"https?://", r["commentaire"]):
        return "sans source cliquable"
    try:
        d = dt.date.fromisoformat(r["date"])
    except ValueError:
        return "sans date"
    if d > aujourd or (aujourd - d).days > DUREE_JOURS:
        return "date hors de l'année écoulée"
    return ""


def appliquer(lieux: pd.DataFrame, ref, v: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Retire les inscriptions que désigne un verdict valable. Renvoie les structures et un compte rendu."""
    from .verdicts import _cles
    v = charger() if v is None else v
    rendu = {"retirees": [], "ecartes": [], "non_trouves": []}
    if v.empty or lieux.empty:
        return lieux, rendu
    nom_com = ref.communes.set_index("code")["nom"]
    retirer = []
    for _, r in v.iterrows():
        raison = valable(r)
        if raison:
            rendu["ecartes"].append({"cle": r["cle"], "type": r["type"], "raison": raison})
            continue
        x = lieux[lieux["type"] == r["type"]]
        trouves = [i for i, s in x.iterrows() if r["cle"] in _cles(s, nom_com)]
        if not trouves:
            rendu["non_trouves"].append({"cle": r["cle"], "type": r["type"]})
            continue
        retirer += trouves
        for i in trouves:
            s = lieux.loc[i]
            rendu["retirees"].append({
                "ej": s.get("ej"), "etablissement": r["etablissement"], "type": r["type"],
                "nom": s.get("nom_affiche") if isinstance(s.get("nom_affiche"), str) else s.get("nom"),
                "commune": s.get("commune"), "nom_commune": nom_com.get(s.get("commune"), ""),
                "finess": s.get("finess") if isinstance(s.get("finess"), str) else None,
                "provenance": s.get("provenance"), "raison": f"vérification à la main, {SORTES[r['verdict']]}"})
    lieux = lieux.drop(index=retirer)
    JOURNAL.controle("Verdicts de la vérification à la main, structures autres que les CMP",
                     f"{len(rendu['retirees'])} inscriptions retirées, {len(rendu['ecartes'])} verdicts écartés "
                     f"(sans source, sans date ou périmés), {len(rendu['non_trouves'])} sans structure correspondante")
    return lieux, rendu
