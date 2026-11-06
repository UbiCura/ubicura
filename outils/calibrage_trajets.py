"""Étude du calibrage des temps de route de la Géoplateforme sur ceux de l'INSEE (demande de la séance principale du
30 octobre 2026, note docs/note_temps_trajet_2026-10-30.md). Lit seulement le cache, aucun appel au service.

    python outils\\calibrage_trajets.py

1. Urgences : nos temps (isochrones, moteur Valhalla sur la BD TOPO) face à ceux de l'INSEE (distancier Metric-OSRM),
   commune par commune, rapport des médianes pondéré par la population, en tout et par classe de densité.
2. Calibrage : un temps de l'INSEE de T minutes correspond chez nous à k × T ; la part des habitants au-delà de T sur
   l'échelle de l'INSEE se lit sur nos tranches (10, 15, 20, 30 et 45 minutes) au seuil k × T, en interpolant la
   fonction de répartition entre deux bornes. Au-delà de 45 × 1 = 45 minutes chez nous, rien n'est lisible sans
   nouvelles isochrones.
3. Validation hors de l'échantillon : établissements psychiatriques (notre hospitalisation complète face à l'équipement
   D104 de l'INSEE) et maternités face à la DREES (Études et Résultats n° 1201, parts à plus de 30 minutes).
Écrit donnees/intermediaire/trajets/national/calibrage.json et affiche le résumé.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config, trajets  # noqa: E402
from pipeline.analyses import medianes_histogramme  # noqa: E402
from pipeline.sources import acces_route, referentiel  # noqa: E402

BORNES = (0, 10, 15, 20, 30, 45)


def insee_communes(ar, code_eq: str) -> pd.DataFrame:
    """Par commune, médiane (histogramme par minute), moyenne et parts à plus de 15, 20 et 30 minutes de l'INSEE."""
    c = ar["communes"]
    x = c[c["typeeq_id"] == code_eq].groupby("depcom")[["pop", "pop_calcule", "pd", "sup_15", "sup_20", "sup_30"]].sum()
    out = pd.DataFrame({"insee_moyen": x["pd"] / x["pop_calcule"].where(x["pop_calcule"] > 0)})
    for s in (15, 20, 30):
        out[f"insee_{s}"] = x[f"sup_{s}"] / x["pop_calcule"].where(x["pop_calcule"] > 0)
    h = ar["histogramme"]
    m = medianes_histogramme(h[h["typeeq_id"] == code_eq], ["depcom"]).set_index("depcom")["temps_median_min"]
    out["insee_median"] = m
    out["insee_pop"] = x["pop_calcule"]
    return out


def part_au_dela(parts: pd.DataFrame, seuil: float) -> pd.Series:
    """Part des habitants au-delà de seuil minutes (notre échelle), lue sur nos tranches : fonction de répartition
    connue aux bornes 10, 15, 20, 30 et 45, interpolée linéairement entre deux bornes, NaN au-delà de 45."""
    au_dela = {0: pd.Series(1.0, index=parts.index), 10: parts.get("part_plus_10_min"),
               15: parts["part_plus_15_min"], 20: parts["part_plus_20_min"], 30: parts["part_plus_30_min"],
               45: parts["part_plus_45_min"]}
    if au_dela[10] is None:
        # pas de part à plus de 10 minutes dans les résumés, interpolée entre 0 et 15
        au_dela[10] = 1 - (1 - au_dela[15]) * 10 / 15
    if seuil > 45:
        return pd.Series(np.nan, index=parts.index)
    for a, b in zip(BORNES[:-1], BORNES[1:]):
        if a <= seuil <= b:
            f = (seuil - a) / (b - a)
            return au_dela[a] * (1 - f) + au_dela[b] * f
    return pd.Series(np.nan, index=parts.index)


def ponderer(s: pd.Series, w: pd.Series) -> float:
    ok = s.notna() & w.notna() & (w > 0)
    return float((s[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else float("nan")


def mediane_ponderee(x: pd.Series, w: pd.Series) -> float:
    ok = x.notna() & np.isfinite(x) & w.notna() & (w > 0)
    x, w = x[ok].to_numpy(), w[ok].to_numpy()
    o = np.argsort(x)
    c = np.cumsum(w[o])
    return float(x[o][np.searchsorted(c, c[-1] / 2)])


def main():
    ref = referentiel.charger(hors_ligne=True)
    ar = acces_route.charger(ref, hors_ligne=True)
    codes = {d["id"]: d["code"] for d in ar["defs"]}
    nat = trajets.DOSSIER / "national"
    com = pd.read_csv(nat / "communes.csv", sep=";", decimal=",", dtype={"code": str})
    terr = pd.read_csv(nat / "territoires.csv", sep=";", decimal=",", dtype={"code": str})
    dossiers = sorted(d for d in config.RESULTATS.glob("20*") if (d / "contexte_com.csv").exists())
    dens = pd.read_csv(dossiers[-1] / "contexte_com.csv", sep=";", decimal=",", dtype={"code": str},
                       usecols=["code", "densite_pop"]).set_index("code")["densite_pop"]
    sortie = {}

    # 1. urgences, rapport des temps par classe de densité
    u = com[com["type"] == "lieu_urgences"].set_index("code").join(insee_communes(ar, codes["urgences"]), how="inner")
    u["densite"] = dens.reindex(u.index)
    u["classe"] = pd.cut(u["densite"], [-1, 50, 300, 1500, np.inf],
                         labels=["rural peu dense (moins de 50 hab./km²)", "rural et périurbain (50 à 300)",
                                 "urbain (300 à 1 500)", "urbain dense (plus de 1 500)"])
    u["rapport"] = u["temps_median_min"] / u["insee_median"].where(u["insee_median"] > 1)
    k_tous = mediane_ponderee(u["rapport"], u["habitants"])
    par_classe = {str(c): {"k": mediane_ponderee(g["rapport"], g["habitants"]), "communes": len(g),
                           "habitants": float(g["habitants"].sum())} for c, g in u.groupby("classe", observed=True)}
    sortie["urgences_rapport"] = {"k_france": k_tous, "par_classe": par_classe}

    # 2. calibrage dans l'échantillon (urgences) : parts à plus de 15, 20 et 30 minutes de l'INSEE
    def k_de(classe):
        return par_classe.get(str(classe), {}).get("k", k_tous)

    def parts_calibrees(df, seuils, par_densite=True):
        out = {}
        for s in seuils:
            if par_densite:
                v = pd.concat([part_au_dela(g, k_de(c) * s) for c, g in df.groupby("classe", observed=True)])
            else:
                v = part_au_dela(df, k_tous * s)
            out[s] = ponderer(v.reindex(df.index), df["habitants"])
        return out

    brut = {s: ponderer(part_au_dela(u, s), u["habitants"]) for s in (15, 20, 30)}
    insee = {s: ponderer(u[f"insee_{s}"], u["insee_pop"]) for s in (15, 20, 30)}
    sortie["urgences_parts"] = {"insee": insee, "brutes": brut, "calibrees_un_k": parts_calibrees(u, (15, 20, 30), False),
                                "calibrees_par_densite": parts_calibrees(u, (15, 20, 30))}

    # 3a. hors de l'échantillon, établissements psychiatriques (INSEE D104) face à notre hospitalisation complète
    h = com[com["type"] == "lieu_hc_psy_adultes"].set_index("code").join(
        insee_communes(ar, codes["etablissement_psychiatrie"]), how="inner")
    h["classe"] = pd.cut(dens.reindex(h.index), [-1, 50, 300, 1500, np.inf],
                         labels=list(par_classe) if len(par_classe) == 4 else None)
    sortie["psychiatrie_hors_echantillon"] = {
        "insee": {s: ponderer(h[f"insee_{s}"], h["insee_pop"]) for s in (15, 20, 30)},
        "brutes": {s: ponderer(part_au_dela(h, s), h["habitants"]) for s in (15, 20, 30)},
        "calibrees_un_k": parts_calibrees(h, (15, 20, 30), False),
        "calibrees_par_densite": parts_calibrees(h, (15, 20, 30)),
        "rapport_median_ici": mediane_ponderee(h["temps_median_min"] / h["insee_median"].where(h["insee_median"] > 1),
                                               h["habitants"])}

    # 3b. maternités face à la DREES (France, part à plus de 30 minutes, autour de 7 % pour les femmes de 15 à 44 ans
    # en 2017) ; les parts à plus de 45 minutes demandent un seuil de 45 × k, au-delà de nos isochrones
    m = com[com["type"] == "lieu_maternite"].set_index("code")
    m["classe"] = pd.cut(dens.reindex(m.index), [-1, 50, 300, 1500, np.inf],
                         labels=list(par_classe) if len(par_classe) == 4 else None)
    sortie["maternites_drees"] = {"drees_2017_plus_30": trajets.REPERE_DREES["france_plus_30"],
                                  "brute_plus_30": ponderer(part_au_dela(m, 30), m["habitants"]),
                                  "calibree_un_k_plus_30": parts_calibrees(m, (30,), False)[30],
                                  "calibree_par_densite_plus_30": parts_calibrees(m, (30,))[30],
                                  "seuil_45_ici_minutes": 45 * k_tous}
    md = terr[(terr["type"] == "lieu_maternite") & (terr["niveau"] == "dep")].set_index("code")
    sortie["maternites_departements_plus_45_brut"] = {d: float(md.at[d, "part_plus_45_min"])
                                                      for d in ("58", "46", "2B", "2A", "04") if d in md.index}
    (nat / "calibrage.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(sortie, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
