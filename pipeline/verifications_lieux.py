"""Vérifications des structures de soins faites sur d'autres sources (sites des établissements, documents des ARS, listes
ouvertes locales), consignées dans contenus/verifications_lieux.csv (décision de Lucas du 13 octobre 2026).

Ce fichier ne corrige aucune donnée. Les chiffres restent ceux de FINESS et du ROR réunis, et une vérification qui
révèle une erreur de règle fait corriger la règle pour toute la France. Il garde, comme les limites de config.LIMITES,
des constats écrits avec leur source et leur date, montrés au lecteur là où la donnée est montrée (rapports
territoriaux, fiche de l'atlas, page méthode). Une vérification de plus de douze mois est signalée comme à refaire."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

FICHIER = Path(__file__).resolve().parents[1] / "contenus" / "verifications_lieux.csv"
COLONNES = ["code", "etablissement", "date", "source", "adresse", "constat"]
VALIDITE_JOURS = 365


def charger() -> pd.DataFrame:
    """Vérifications consignées, une ligne par constat, avec l'indication « à refaire » au-delà de douze mois."""
    if not FICHIER.exists():
        return pd.DataFrame(columns=COLONNES + ["a_refaire"])
    t = pd.read_csv(FICHIER, sep=";", dtype=str, encoding="utf-8").fillna("")
    manque = [c for c in COLONNES if c not in t]
    if manque:
        raise ValueError(f"colonnes absentes de {FICHIER.name}, {manque}")
    d = pd.to_datetime(t["date"], errors="coerce")
    t["a_refaire"] = (pd.Timestamp(date.today()) - d).dt.days > VALIDITE_JOURS
    return t


def phrases_md(t: pd.DataFrame, codes) -> list[str]:
    """Constats des territoires demandés, au format Markdown, avec leur source cliquable et leur date."""
    from .lecture import date_longue
    x = t[t["code"].isin(set(codes))]
    out = []
    for _, r in x.iterrows():
        quand = date_longue(r["date"]) if r["date"] else ""
        out.append(f"{r['constat']} Source, [{r['source']}]({r['adresse']}), consultée le {quand}"
                   + (", vérification à refaire." if r["a_refaire"] else "."))
    return out
