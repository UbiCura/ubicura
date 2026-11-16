"""Mesure nationale de la liste des structures de soins, en lecture seule (chantier des structures, étape 0).

Refait depuis les fichiers d'une édition (resultats/<édition>/) les chiffres de la fiche de préparation
docs/revue_plan_2026-11-16/chantier_structures_de_soins.md, partie 2, et les compare aux chiffres qu'elle écrit.
N'écrit que dans docs/structures/mesure_<date>/ : rien dans resultats/, site/ ni le catalogue.

    python outils\\mesure_structures.py [--edition 2026-11-13]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))

# chiffres écrits dans la fiche de préparation du 15 novembre 2026 (partie 2), que l'étape 0 doit retrouver
ATTENDU = {
    "cmp_liste": 2739, "cmp_sae": 2922, "adultes_liste": 1511, "adultes_sae": 1623, "enfants_liste": 1188,
    "enfants_sae": 1299,
    "dep_total_moins50": 8, "dep_total_20_50": 10, "dep_total_plus20": 16,
    "dep_adultes_moins50": 8, "dep_adultes_20_50": 12, "dep_enfants_moins50": 6, "dep_enfants_moins20": 23,
    "etab_n": 274, "etab_sae_cmp": 2922, "etab_ici_cmp": 2733, "etab_moins_n": 100, "etab_moins_cmp": 424,
    "etab_plus_avec_absents_n": 95, "etab_plus_avec_absents_cmp": 235, "etab_absents_n": 8, "etab_absents_cmp": 9,
    "communes_20k": 484, "communes_20k_sans_cmp_adultes": 112, "communes_20k_5km_adultes": 20,
    "communes_20k_5km_enfants": 33,
    "epci_50k": 287, "epci_50k_sans_cmp_adultes": 13, "epci_50k_sans_cmp_enfants": 23,
    "doublons_adultes_groupes": 154, "doublons_adultes_structures": 418, "doublons_adultes_ror_seul": 44,
    "doublons_adultes_meme_adresse_ecrite": 27,
    "doublons_enfants_groupes": 144, "doublons_enfants_structures": 373, "doublons_enfants_ror_seul": 50,
    "doublons_enfants_meme_adresse_ecrite": 21,
    "doublons_cattp_groupes": 334, "doublons_cattp_structures": 909, "doublons_cattp_ror_seul": 212,
    "doublons_cattp_meme_adresse_ecrite": 48,
}


def lire(chemin: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(chemin, sep=";", decimal=",", encoding="utf-8-sig", dtype=str, keep_default_na=False, **kw)


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.replace(",", ".", regex=False).replace("", None), errors="coerce")


def ecart(ici: pd.Series, sae: pd.Series) -> pd.Series:
    return (ici / sae.where(sae > 0)) - 1


def mesurer(ed: Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    m, tables = {}, {}
    # 1. totaux et départements, sur la concordance avec la SAE
    c = lire(ed / "concordance_cmp_sae.csv")
    d = c[c["niveau"] == "dep"].copy()
    for k in ("cmp", "adultes", "enfants", "sae_cmp", "sae_adultes", "sae_enfants"):
        d[k] = num(d[k])
    m.update(cmp_liste=int(d["cmp"].sum()), cmp_sae=int(d["sae_cmp"].sum()), adultes_liste=int(d["adultes"].sum()),
             adultes_sae=int(d["sae_adultes"].sum()), enfants_liste=int(d["enfants"].sum()),
             enfants_sae=int(d["sae_enfants"].sum()))
    d["e_total"], d["e_adultes"], d["e_enfants"] = (ecart(d["cmp"], d["sae_cmp"]), ecart(d["adultes"], d["sae_adultes"]),
                                                   ecart(d["enfants"], d["sae_enfants"]))
    # masqué : les bases inscrivent moins de la moitié de ce que la SAE déclare (pipeline/lieux.py, SAE_PART_MIN, règle
    # stricte : un département à 50 % tout juste n'est pas masqué)
    m.update(dep_total_moins50=int((d["e_total"] < -.5).sum()),
             dep_total_20_50=int(((d["e_total"] >= -.5) & (d["e_total"] <= -.2)).sum()),
             dep_total_plus20=int((d["e_total"] >= .2).sum()),
             dep_adultes_moins50=int((d["e_adultes"] < -.5).sum()),
             dep_adultes_20_50=int(((d["e_adultes"] >= -.5) & (d["e_adultes"] <= -.2)).sum()),
             dep_enfants_moins50=int((d["e_enfants"] < -.5).sum()),
             dep_enfants_50_tout_juste=int((d["e_enfants"] == -.5).sum()),
             dep_enfants_moins20=int((d["e_enfants"] <= -.2).sum()))
    m["liste_dep_adultes_moins50"] = " ".join(sorted(d.loc[d["e_adultes"] < -.5, "code"]))
    m["liste_dep_enfants_moins50"] = " ".join(sorted(d.loc[d["e_enfants"] < -.5, "code"]))
    m["liste_dep_enfants_50_tout_juste"] = " ".join(sorted(d.loc[d["e_enfants"] == -.5, "code"]))
    m["liste_dep_total_20_50"] = ", ".join(d.loc[(d["e_total"] >= -.5) & (d["e_total"] <= -.2), "nom"])
    tables["departements_concordance"] = d[["code", "nom", "cmp", "sae_cmp", "e_total", "adultes", "sae_adultes",
                                            "e_adultes", "enfants", "sae_enfants", "e_enfants"]]
    # 2. établissements
    e = lire(ed / "concordance_cmp_etablissements.csv")
    for k in ("sae_cmp", "ici_cmp"):
        e[k] = num(e[k]).fillna(0)
    dif = e["ici_cmp"] - e["sae_cmp"]
    abs_ = e["statut"].str.contains("absent", case=False)
    m.update(etab_n=len(e), etab_sae_cmp=int(e["sae_cmp"].sum()), etab_ici_cmp=int(e["ici_cmp"].sum()),
             etab_moins_n=int(((dif < 0) & ~abs_).sum()), etab_moins_cmp=int(-dif[(dif < 0) & ~abs_].sum()),
             etab_plus_n=int(((dif > 0) & ~abs_).sum()), etab_plus_cmp=int(dif[(dif > 0) & ~abs_].sum()),
             # la fiche du 15 novembre compte les établissements absents de la SAE parmi ceux qui ont plus de CMP ici
             etab_plus_avec_absents_n=int((dif > 0).sum()), etab_plus_avec_absents_cmp=int(dif[dif > 0].sum()),
             etab_absents_n=int(abs_.sum()), etab_absents_cmp=int(e.loc[abs_, "ici_cmp"].sum()))
    # 3. grandes communes : population lue une fois par commune, distance au plus proche
    pop = lire(ed / "accessibilite_communes.csv", usecols=["code", "population"]).drop_duplicates("code")
    pop["population"] = num(pop["population"])
    dc = lire(ed / "distances_lieux_communes.csv").merge(pop, on="code", how="left")
    L = lire(ed / "lieux_soins.csv", on_bad_lines="warn")
    g = dc[dc["population"] >= 20000].copy()
    ca = set(L.loc[L["type"] == "lieu_cmp_adultes", "commune"])
    m["communes_20k"] = len(g)
    m["communes_20k_sans_cmp_adultes"] = int((~g["code"].isin(ca)).sum())
    for t, k in (("adultes", "dist_lieu_cmp_adultes"), ("enfants", "dist_lieu_cmp_enfants")):
        g[k] = num(g[k])
        m[f"communes_20k_5km_{t}"] = int((g[k] >= 5).sum())
    tables["grandes_communes_cmp"] = g[["code", "nom", "dep", "population", "dist_lieu_cmp_adultes",
                                        "dist_lieu_cmp_enfants"]].sort_values("population", ascending=False)
    # 4. grandes intercommunalités
    ep = lire(ed / "lieux_soins_epci.csv")
    ep["population"] = num(ep["population"])
    G = ep[ep["population"] >= 50000]
    m["epci_50k"] = len(G)
    m["epci_50k_sans_cmp_adultes"] = int((num(G["n_lieu_cmp_adultes"]) == 0).sum())
    m["epci_50k_sans_cmp_enfants"] = int((num(G["n_lieu_cmp_enfants"]) == 0).sum())
    # 5. groupes à examiner pour les doublons : même gestionnaire, même type, même commune
    for t, ty in (("adultes", "lieu_cmp_adultes"), ("enfants", "lieu_cmp_enfants"), ("cattp", "lieu_cattp")):
        x = L[(L["type"] == ty) & (L["entite_juridique"] != "")]
        grp = x.groupby(["entite_juridique", "commune"])
        taille = grp["id_structure"].transform("size")
        x = x[taille > 1]
        gg = x.groupby(["entite_juridique", "commune"])
        m[f"doublons_{t}_groupes"] = gg.ngroups
        m[f"doublons_{t}_structures"] = len(x)
        m[f"doublons_{t}_ror_seul"] = int(gg["provenance"].apply(lambda s: (s == "ROR seul").any()).sum())
        adr = x["adresse"]
        m[f"doublons_{t}_meme_adresse_ecrite"] = int(adr.groupby([x["entite_juridique"], x["commune"]])
                                                     .apply(lambda s: s[s != ""].duplicated().any()).sum())
        adr = x["adresse"].str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
        m[f"doublons_{t}_meme_adresse"] = int(adr.groupby([x["entite_juridique"], x["commune"]])
                                              .apply(lambda s: s[s != ""].duplicated().any()).sum())
    m["lignes_lieux_soins"] = len(L)
    return m, tables


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", default=None)
    a = ap.parse_args()
    eds = sorted(p for p in (R / "resultats").iterdir() if p.is_dir() and p.name[:2] == "20")
    ed = R / "resultats" / a.edition if a.edition else eds[-1]
    m, tables = mesurer(ed)
    out = R / "docs" / "structures" / f"mesure_{dt.date.today().isoformat()}"
    out.mkdir(parents=True, exist_ok=True)
    lignes, ecarts = [], 0
    for k, v in m.items():
        att = ATTENDU.get(k)
        ok = "" if att is None else ("ok" if att == v else f"ÉCART (fiche : {att})")
        ecarts += ok.startswith("ÉCART")
        lignes.append((k, v, ok))
    pd.DataFrame(lignes, columns=["mesure", "valeur", "comparaison_fiche"]).to_csv(
        out / "etape0_mesures.csv", sep=";", index=False, encoding="utf-8-sig")
    for n, t in tables.items():
        t.to_csv(out / f"etape0_{n}.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    for k, v, ok in lignes:
        print(f"{k:38} {v!s:>40}  {ok}")
    print(f"\nÉdition {ed.name}, {ecarts} écart(s) avec la fiche. Dossier {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
