"""D'où vient l'écart entre nos temps de route et ceux de l'INSEE ? Décomposition sur les urgences (demande de la
séance principale du 31 octobre 2026, note docs/note_temps_trajet_2026-10-30.md). Lit seulement le cache.

    python outils\\decomposition_trajets.py

Faits établis sur la note de l'INSEE (« Localisation et accès de la population aux équipements », note explicative,
15 juillet 2025) : origine, les carreaux de 200 m de population, comme ici ; destination, les équipements de la BPE
géolocalisés (le chef-lieu de la commune à défaut), et l'équipement D106 regroupe, d'après la liste des équipements de
la BPE 2025, les services d'intervention (SAMU-SMUR) et d'accueil des urgences ; moteur, Metric-OSRM sur OpenStreetMap
2022, profil voiture ; durée minimale de 1 minute.

Parts comparées aux bornes exactes de nos tranches (15, 20 et 30 minutes), sans interpolation :
1. toutes les communes ;
2. communes où un SMUR que nous recensons est plus proche que tout service d'urgences (destination différente) ;
3. communes où le temps de l'INSEE est impossible avec nos structures (plus rapide que 100 km/h à vol d'oiseau jusqu'à
   notre service d'urgences ou notre SMUR le plus proche), l'INSEE y a donc un équipement que nous n'avons pas ;
4. le reste, même destination probable : ce qui reste de l'écart tient au moteur et au réseau ; par densité ;
5. communes dont le service d'urgences le plus proche n'a pas d'adresse précise (centre de sa commune).
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
from pipeline.sources import acces_route, referentiel  # noqa: E402
sys.path.insert(0, str(RACINE / "outils"))
from calibrage_trajets import insee_communes, ponderer  # noqa: E402


def parts(df):
    """Parts à plus de 15, 20 et 30 minutes, ici et pour l'INSEE, pondérées par les habitants."""
    return {"communes": len(df), "habitants": float(df["habitants"].sum()),
            **{f"ici_{s}": round(ponderer(df[f"part_plus_{s}_min"], df["habitants"]), 4) for s in (15, 20, 30)},
            **{f"insee_{s}": round(ponderer(df[f"insee_{s}"], df["insee_pop"]), 4) for s in (15, 20, 30)}}


def main():
    ref = referentiel.charger(hors_ligne=True)
    ar = acces_route.charger(ref, hors_ligne=True)
    codes = {d["id"]: d["code"] for d in ar["defs"]}
    nat = trajets.DOSSIER / "national"
    com = pd.read_csv(nat / "communes.csv", sep=";", decimal=",", dtype={"code": str})
    d = sorted(x for x in config.RESULTATS.glob("20*") if (x / "distances_lieux_communes.csv").exists())[-1]
    dist = pd.read_csv(d / "distances_lieux_communes.csv", sep=";", decimal=",", dtype={"code": str, "dep": str}).set_index("code")
    dens = pd.read_csv(d / "contexte_com.csv", sep=";", decimal=",", dtype={"code": str},
                       usecols=["code", "densite_pop"]).set_index("code")["densite_pop"]
    u = com[com["type"] == "lieu_urgences"].set_index("code").join(insee_communes(ar, codes["urgences"]), how="inner")
    # distance au SMUR le plus proche, à vol d'oiseau depuis le centre de la population de la commune, comme nos
    # distances (le SMUR n'est pas un type suivi par distances_lieux_communes)
    centres = pd.read_parquet(config.INTER / "centres_population_communes.parquet").set_index("code")[["lon", "lat"]]
    l0 = pd.read_csv(d / "lieux_soins.csv", sep=";", dtype=str, usecols=["type", "latitude", "longitude"])
    sm = l0[l0["type"] == "lieu_smur"].copy()
    for c in ("latitude", "longitude"):
        sm[c] = pd.to_numeric(sm[c].str.replace(",", ".", regex=False), errors="coerce")
    sm = sm.dropna()
    c = centres.reindex(u.index)
    lat1, lon1 = np.radians(c["lat"].to_numpy())[:, None], np.radians(c["lon"].to_numpy())[:, None]
    lat2, lon2 = np.radians(sm["latitude"].to_numpy())[None, :], np.radians(sm["longitude"].to_numpy())[None, :]
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    u["dist_lieu_smur"] = (2 * 6371 * np.arcsin(np.sqrt(h))).min(axis=1)
    u = u.join(dist[["dist_lieu_urgences"]], how="left")
    u["densite"] = dens.reindex(u.index)
    d_su, d_sm = u["dist_lieu_urgences"], u["dist_lieu_smur"]
    smur_plus_proche = d_sm < d_su - 2
    d_min = np.fmin(d_su, d_sm)
    impossible = u["insee_moyen"] < 0.6 * d_min - 1
    meme = ~smur_plus_proche & ~impossible
    out = {"toutes": parts(u), "smur_plus_proche_que_les_urgences": parts(u[smur_plus_proche]),
           "insee_a_un_equipement_absent_ici": parts(u[impossible & ~smur_plus_proche]),
           "meme_destination_probable": parts(u[meme])}
    classes = pd.cut(u["densite"], [-1, 50, 300, 1500, np.inf], labels=["moins de 50", "50 à 300", "300 à 1 500", "plus de 1 500"])
    out["meme_destination_par_densite"] = {str(c): parts(g) for c, g in u[meme].groupby(classes[meme], observed=True)}
    # adresses approchées : services d'urgences placés au centre de leur commune
    l = pd.read_csv(d / "lieux_soins.csv", sep=";", dtype=str, usecols=["type", "commune", "emplacement"])
    centre = set(l.loc[(l["type"] == "lieu_urgences") & l["emplacement"].fillna("").str.startswith("centre de la commune"),
                       "commune"])
    out["urgences_au_centre_de_leur_commune"] = {"structures": int(len(l[(l["type"] == "lieu_urgences") & l["commune"].isin(centre)])),
                                                 "communes_concernees_dont_la_leur": parts(u[u.index.isin(centre)])}
    (nat / "decomposition.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
