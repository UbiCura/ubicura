"""Banc d'essai de la liste des structures : recalcule pipeline.lieux.calculer depuis les fichiers en cache, sans rien
écrire dans resultats/ ni site/, et garde la liste obtenue pour la comparer d'une règle à l'autre.

    python outils\\essai_lieux.py <etiquette>        écrit D:\\offre_soins_tmp\\essai_lieux\\<etiquette>.parquet
    python outils\\essai_lieux.py --comparer a b      compare deux listes : structures par type, ajoutées, retirées, déplacées

Exécution lourde (FINESS, ROR, RPPS) : une seule à la fois sur la machine, avec au moins 6 Go libres.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
DOSSIER = Path(r"D:\offre_soins_tmp\essai_lieux")


def calculer(etiquette: str) -> Path:
    from pipeline import config, lieux
    from pipeline.sources import finess, has_certification, has_essms, optionnels, referentiel, ror, sirene
    hl, rf = True, False
    ref = referentiel.charger(hl, rf)
    act = pd.read_parquet(config.INTER / "rpps_activites.parquet")
    fin = finess.charger(hl, rf)
    voisins = optionnels.voisinages(ref, hl, rf)
    res = lieux.calculer(ror.charger(hl, rf), fin, act, ref, voisins, hl,
                         has_certification.charger(hl, rf), sirene.charger(hl, rf), has_essms.charger(hl, rf))
    DOSSIER.mkdir(parents=True, exist_ok=True)
    x = res["lieux"].copy()
    for c in x.columns:
        if x[c].dtype == object:
            x[c] = x[c].astype(str)
    out = DOSSIER / f"{etiquette}.parquet"
    x.to_parquet(out, index=False)
    print(f"{len(x)} lignes, {out}")
    return out


def comparer(a: str, b: str) -> None:
    A, B = (pd.read_parquet(DOSSIER / f"{e}.parquet") for e in (a, b))
    cle = "lieu" if "lieu" in A.columns else "id_structure"
    t = pd.DataFrame({a: A.groupby("type").size(), b: B.groupby("type").size()}).fillna(0).astype(int)
    t["ecart"] = t[b] - t[a]
    print(t[t["ecart"] != 0].to_string())
    ka, kb = set(zip(A[cle], A["type"])), set(zip(B[cle], B["type"]))
    print(f"ajoutées {len(kb - ka)}, retirées {len(ka - kb)}")
    com = "commune"
    m = A[[cle, "type", com]].merge(B[[cle, "type", com]], on=[cle, "type"], suffixes=("_a", "_b"))
    dep = m[m[f"{com}_a"] != m[f"{com}_b"]]
    print(f"déplacées {len(dep)}")
    dep.to_csv(DOSSIER / f"deplacees_{a}_{b}.csv", sep=";", index=False, encoding="utf-8-sig")


def unites(finess_: list[str]) -> None:
    """Unités du ROR rattachées à ces établissements (numéro FINESS de la structure de rattachement), avec leur
    catégorie, leur champ, leur mode et leur commune : pour comprendre pourquoi une activité manque à la liste."""
    from pipeline.sources import ror
    r = ror.charger(True, False)
    u, s = r["unites"], r["structures"]
    cles = set(s.loc[s["finess"].isin(finess_), "cle"])
    x = u[u["structures"].fillna("").map(lambda v: bool(cles & set(v.split("|"))))]
    cols = [c for c in ("nom", "categorie", "champ", "mode", "niveau_organisation", "commune", "type_maternite") if c in x]
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(x[cols].to_string())


if __name__ == "__main__":
    if sys.argv[1] == "--comparer":
        comparer(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "--unites":
        unites(sys.argv[2:])
    else:
        calculer(sys.argv[1])
