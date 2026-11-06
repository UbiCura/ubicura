"""Structures restées au centre de leur commune faute d'adresse trouvée : lesquelles comptent le plus ? (chantier des
structures précises, demande de la séance principale du 31 octobre 2026). Lecture seule de la dernière version.

    python outils\\enjeu_adresses.py [types séparés par des virgules]

Pour chaque structure placée au centre de sa commune, l'enjeu est le nombre d'habitants dont elle est la structure la plus
proche de son type (à vol d'oiseau depuis le centre de la population de leur commune, comme les distances du site),
multiplié par l'erreur de position possible, le rayon d'un disque de la surface de sa commune (contours de l'IGN en
cache). Écrit docs/structures_a_localiser.csv, trié par enjeu, avec la cause (pas d'adresse, adresse non trouvée,
adresse du gestionnaire reprise), à traiter dans cet ordre sur les sources des établissements.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402

TYPES = ["lieu_cmp_adultes", "lieu_cmp_enfants", "lieu_cattp", "lieu_hdj_psy_adultes", "lieu_hdj_psy_enfants",
         "lieu_hc_psy_adultes", "lieu_cmpp", "lieu_camsp", "lieu_csapa", "lieu_urgences", "lieu_maternite"]


def plus_proche(lon1, lat1, lon2, lat2):
    """Indice de la structure la plus proche de chaque point (distance sur la sphère)."""
    p1 = np.radians(np.c_[lat1, lon1])
    p2 = np.radians(np.c_[lat2, lon2])
    out = np.empty(len(p1), dtype=int)
    for i in range(0, len(p1), 2000):
        a = p1[i:i + 2000, None, :]
        h = (np.sin((p2[None, :, 0] - a[..., 0]) / 2) ** 2
             + np.cos(a[..., 0]) * np.cos(p2[None, :, 0]) * np.sin((p2[None, :, 1] - a[..., 1]) / 2) ** 2)
        out[i:i + 2000] = h.argmin(axis=1)
    return out


def main(types=TYPES):
    d = sorted(x for x in config.RESULTATS.glob("20*") if (x / "lieux_soins.csv").exists())[-1]
    l = pd.read_csv(d / "lieux_soins.csv", sep=";", dtype=str)
    for c in ("latitude", "longitude"):
        l[c] = pd.to_numeric(l[c].str.replace(",", ".", regex=False), errors="coerce")
    cen = pd.read_parquet(config.INTER / "centres_population_communes.parquet").set_index("code")
    pop = {c["code"]: c.get("population") or 0 for c in json.loads((config.BRUT / "ref_communes.json").read_text(encoding="utf-8"))
           if c.get("type") == "commune-actuelle"}
    # surface des communes d'après le fond des communes en cache (km²), rayon d'erreur possible
    surf = {}
    fonds = config.INTER / "fonds_communes.json"
    if fonds.exists():
        import shapely
        # {"fonds": {département: {commune: WKT}}}, contours simplifiés de l'IGN
        for dep in json.loads(fonds.read_text(encoding="utf-8"))["fonds"].values():
            for code, wkt in dep.items():
                g = shapely.from_wkt(wkt)
                surf[code] = g.area * 111.32 ** 2 * np.cos(np.radians(g.centroid.y))
    cen = cen[cen.index.isin(pop)]
    lignes = []
    for t in types:
        s = l[(l["type"] == t)].dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
        if s.empty:
            continue
        k = plus_proche(cen["lon"].to_numpy(), cen["lat"].to_numpy(), s["longitude"].to_numpy(), s["latitude"].to_numpy())
        hab = pd.Series([pop.get(c, 0) for c in cen.index]).groupby(k).sum()
        s["habitants_servis"] = s.index.map(hab).fillna(0)
        app = s[s["emplacement"].fillna("").str.startswith("centre de la commune")].copy()
        app["rayon_km"] = app["commune"].map(lambda c: np.sqrt(surf.get(c, np.nan) / np.pi) if c in surf else np.nan)
        app["enjeu"] = app["habitants_servis"] * app["rayon_km"].fillna(1)
        app["cause"] = np.where(app["adresse"].fillna("").str.strip() == "", "pas d'adresse",
                                np.where(app["emplacement"].str.contains("gestionnaire"), "adresse du gestionnaire reprise",
                                         "adresse non trouvée"))
        lignes.append(app)
    t = pd.concat(lignes).sort_values("enjeu", ascending=False)
    cols = ["id_structure", "type", "nom", "nom_commune", "commune", "dep", "adresse", "cause", "habitants_servis",
            "rayon_km", "enjeu", "finess", "entite_juridique"]
    t = t[[c for c in cols if c in t]]
    sortie = RACINE / "docs" / "structures_a_localiser.csv"
    t.to_csv(sortie, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    print(len(t), "structures, enjeu cumulé des 50 premières", f"{t['enjeu'].head(50).sum() / t['enjeu'].sum():.0%}")
    print(t.groupby("cause").size().to_string())
    print(t.head(25)[["type", "nom", "nom_commune", "cause", "habitants_servis", "rayon_km"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else TYPES)
