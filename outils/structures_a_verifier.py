"""Structures de soins encore à vérifier, regroupées par établissement gestionnaire (22 octobre 2026).

Prépare les courriels aux établissements (point 3 de l'ordre de Lucas). Une ligne par structure dont la classe de
confirmation est « à vérifier », pour tous les types confrontés à des listes indépendantes (CATTP, hôpitaux de jour,
CMPP, CAMSP, CSAPA...), avec son gestionnaire (entité juridique de FINESS et sa dénomination) et, pour les CATTP, le
nombre que l'hôpital déclare à la SAE face au nombre recensé ici. Écrit dans docs/verification/ :

- structures_a_verifier.csv, une ligne par structure ;
- gestionnaires_a_verifier.csv, une ligne par gestionnaire, du plus grand nombre de structures à vérifier au plus petit.

    .\\.venv\\Scripts\\python.exe outils\\structures_a_verifier.py [AAAA-MM-JJ]

Aucune donnée personnelle, seulement des établissements et leurs adresses publiques.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "docs" / "verification"


def dossier(version: str | None) -> Path:
    r = RACINE / "resultats"
    if version:
        return r / version
    return max((d for d in r.iterdir() if d.is_dir() and d.name[:4].isdigit() and (d / "lieux_soins.csv").exists()),
               key=lambda d: d.name)


def noms_gestionnaires() -> dict:
    """Dénomination de chaque entité juridique de FINESS (Finess+), longue si elle existe."""
    f = RACINE / "donnees" / "brut" / "finess_plus.json.gz"
    if not f.exists():
        return {}
    d = json.load(gzip.open(f, "rt", encoding="utf-8"))
    out = {}
    for pm in d.get("pmej", []):
        i = pm.get("informationsGeneralesPMEJ") or {}
        if i.get("numFinessPm"):
            out[str(i["numFinessPm"])] = i.get("denominationLonguePmSmsse") or i.get("denominationPm") or ""
    return out


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    d = dossier(argv[0] if argv else None)
    x = pd.read_csv(d / "lieux_soins.csv", sep=";", dtype=str, encoding="utf-8-sig")
    av = x[x["classe_confirmation"].fillna("").str.contains("vérifier")].copy()
    noms = noms_gestionnaires()
    c = d / "concordance_cmp_etablissements.csv"
    sae = (pd.read_csv(c, sep=";", dtype=str, encoding="utf-8-sig").set_index("ej") if c.exists() else pd.DataFrame())
    av["gestionnaire"] = av["entite_juridique"].map(noms).fillna("")
    if len(sae):
        manque = av["gestionnaire"].eq("") & av["entite_juridique"].isin(sae.index)
        av.loc[manque, "gestionnaire"] = av.loc[manque, "entite_juridique"].map(sae["nom"]).fillna("")
    av["type_court"] = av["libelle_type"].str.split(",").str[0]
    cols = ["entite_juridique", "gestionnaire", "dep", "type", "type_court", "nom", "adresse", "nom_commune", "finess",
            "unite_ror", "provenance", "confirmation"]
    SORTIE.mkdir(parents=True, exist_ok=True)
    av[cols].sort_values(["entite_juridique", "type", "nom_commune", "nom"]).to_csv(
        SORTIE / "structures_a_verifier.csv", sep=";", index=False, encoding="utf-8-sig")

    g = av.pivot_table(index="entite_juridique", columns="type_court", values="nom", aggfunc="count", fill_value=0)
    g["total"] = g.sum(axis=1)
    info = av.groupby("entite_juridique").agg(gestionnaire=("gestionnaire", "first"),
                                              departements=("dep", lambda s: ", ".join(sorted(set(s.dropna())))))
    g = info.join(g)
    if len(sae):
        for k in ("sae_cattp", "ici_cattp", "statut_cattp"):
            if k in sae:
                g[k] = sae[k].reindex(g.index)
    g = g.sort_values(["total", "gestionnaire"], ascending=[False, True])
    g.reset_index().to_csv(SORTIE / "gestionnaires_a_verifier.csv", sep=";", index=False, encoding="utf-8-sig")

    print(f"{len(av)} structures à vérifier, {g.shape[0]} gestionnaires, version {d.name}")
    print(av["type_court"].value_counts().to_string())
    print(f"gestionnaires sans dénomination, {int(g['gestionnaire'].eq('').sum())}")
    print(f"structures sans gestionnaire, {int(av['entite_juridique'].isna().sum())}")
    print(f"les dix gestionnaires qui en ont le plus regroupent {int(g['total'].head(10).sum())} structures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
