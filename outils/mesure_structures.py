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


def normaliser(s: pd.Series) -> pd.Series:
    return s.str.upper().str.replace(r"\s+", " ", regex=True).str.strip()


def etape1(ed: Path) -> dict[str, pd.DataFrame]:
    """M1 et M3. La SAE déclare ses CMP par établissement géographique de l'hôpital (FI, pipeline/sources/sae.py), pas
    par lieu de consultation : la concordance la plus fine qu'elle permet est l'établissement, ramené à son entité
    juridique actuelle (concordance_cmp_etablissements.csv). On liste, par type, les établissements où la liste a moins
    de structures que la SAE ; puis les groupes de même gestionnaire, même type, même commune, classés par cas."""
    T = {}
    e = lire(ed / "concordance_cmp_etablissements.csv")
    for k in ("sae_adultes", "sae_enfants", "sae_cattp", "ici_adultes", "ici_enfants", "ici_cattp"):
        e[k] = num(e[k]).fillna(0).astype(int)
    lignes = []
    for t in ("adultes", "enfants", "cattp"):
        x = e[e[f"ici_{t}"] < e[f"sae_{t}"]]
        for _, r in x.iterrows():
            lignes.append({"type": t, "ej": r["ej"], "nom": r["nom"], "dep_siege": r["dep_siege"],
                           "sae": r[f"sae_{t}"], "ici": r[f"ici_{t}"], "manque": r[f"sae_{t}"] - r[f"ici_{t}"]})
    T["etape1_etablissements_moins_que_sae"] = pd.DataFrame(lignes).sort_values(["type", "manque"], ascending=[True, False])
    L = lire(ed / "lieux_soins.csv")
    out = []
    for t, ty in (("CMP pour adultes", "lieu_cmp_adultes"), ("CMP pour enfants", "lieu_cmp_enfants"), ("CATTP", "lieu_cattp")):
        x = L[(L["type"] == ty) & (L["entite_juridique"] != "")].copy()
        x["adr"] = normaliser(x["adresse"])
        for (ej, com), g in x.groupby(["entite_juridique", "commune"]):
            if len(g) < 2:
                continue
            adr = g["adr"][g["adr"] != ""]
            siret = g["siret_sirene"][g["siret_sirene"] != ""]
            meme_adr = adr.duplicated(keep=False)
            # même adresse et même SIRET pour au moins deux structures : seul cas que la mesure appelle « doublon
            # probable » ; une même adresse seule reste « à examiner » (deux structures distinctes au même lieu comptent
            # pour deux, docs/reperes_donnees.md)
            cle = g.loc[meme_adr.reindex(g.index, fill_value=False) & (g["siret_sirene"] != "")]
            doublon = bool(len(cle) and cle.duplicated(["adr", "siret_sirene"], keep=False).any())
            cas = ("même adresse et même SIRET" if doublon else "même adresse, SIRET distincts ou absents"
                   if meme_adr.any() else "adresses distinctes")
            out.append({"type": t, "entite_juridique": ej, "commune": com, "nom_commune": g["nom_commune"].iloc[0],
                        "dep": g["dep"].iloc[0], "structures": len(g), "cas": cas,
                        "ror_seul": int((g["provenance"] == "ROR seul").sum()),
                        "siret_distincts": siret.nunique(), "sans_siret": int((g["siret_sirene"] == "").sum()),
                        "noms": " | ".join(g["nom"].str.slice(0, 60)), "adresses": " | ".join(g["adresse"]),
                        "ids": " ".join(g["id_structure"])})
    D = pd.DataFrame(out)
    T["etape1_groupes_doublons"] = D
    T["etape1_groupes_doublons_resume"] = (D.groupby(["type", "cas"]).agg(groupes=("structures", "size"),
                                                                        structures=("structures", "sum")).reset_index())
    return T


TYPES_M2 = ("cmp_adultes", "cmp_enfants", "cattp", "hdj_psy_adultes", "hdj_psy_enfants", "cmpp", "csapa", "pmi",
            "maternite", "urgences", "dialyse", "had", "smr")


def etape2(ed: Path) -> dict[str, pd.DataFrame]:
    """M2 : grandes communes loin de toute structure d'un type, grandes intercommunalités sans structure du type, et le
    nombre de signaux que donne chaque seuil voisin. Une distance vide est une distance non publiée (département masqué)."""
    T = {}
    pop = lire(ed / "accessibilite_communes.csv", usecols=["code", "population"]).drop_duplicates("code")
    pop["population"] = num(pop["population"])
    dc = lire(ed / "distances_lieux_communes.csv").merge(pop, on="code", how="left")
    ep = lire(ed / "lieux_soins_epci.csv")
    ep["population"] = num(ep["population"])
    sens, sig = [], []
    for t in TYPES_M2:
        dist = num(dc[f"dist_lieu_{t}"])
        for pmin in (10000, 20000, 30000):
            for km in (3, 5, 8):
                sens.append({"type": t, "niveau": "commune", "population_min": pmin, "km_min": km,
                             "signaux": int(((dc["population"] >= pmin) & (dist >= km)).sum()),
                             "non_publies": int(((dc["population"] >= pmin) & dist.isna()).sum())})
        n = num(ep[f"n_lieu_{t}"])
        for pmin in (30000, 50000, 100000):
            sens.append({"type": t, "niveau": "intercommunalité", "population_min": pmin, "km_min": None,
                         "signaux": int(((ep["population"] >= pmin) & (n == 0)).sum()), "non_publies": None})
        x = dc[(dc["population"] >= 20000) & (dist >= 5)]
        for _, r in x.iterrows():
            sig.append({"type": t, "niveau": "commune", "code": r["code"], "nom": r["nom"], "dep": r["dep"],
                        "population": int(r["population"]), "distance_km": round(float(num(pd.Series([r[f"dist_lieu_{t}"]]))[0]), 1)})
        x = ep[(ep["population"] >= 50000) & (n == 0)]
        for _, r in x.iterrows():
            sig.append({"type": t, "niveau": "intercommunalité", "code": r["code"], "nom": r["nom"], "dep": "",
                        "population": int(r["population"]), "distance_km": None})
    T["etape2_sensibilite_seuils"] = pd.DataFrame(sens)
    S = pd.DataFrame(sig)
    S["cause"], S["source"], S["date_source"], S["remarque"] = "", "", "", ""
    T["etape2_signaux"] = S.sort_values(["type", "niveau", "population"], ascending=[True, True, False])
    return T


APPARENTES = ("lieu_cmp", "lieu_cmp_adultes", "lieu_cmp_enfants", "lieu_consult_psy", "lieu_cattp",
              "lieu_hdj_psy_adultes", "lieu_hdj_psy_enfants", "lieu_cmpp", "lieu_hc_psy_adultes", "lieu_hc_psy_enfants",
              "lieu_mda", "lieu_crise_psy", "lieu_mobile_psy")


def contexte_cmp(ed: Path, signaux: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque signal des CMP : les deux structures du type les plus proches du centre de la population (même calcul
    que pipeline/lieux.distances, à vol d'oiseau), les structures de psychiatrie déjà inscrites dans la commune ou
    l'intercommunalité, la concordance du département avec la SAE et les gestionnaires du type dans le département."""
    import numpy as np
    from pipeline import config, zone
    C = zone.centres(config.BRUT, config.INTER)
    L = lire(ed / "lieux_soins.csv")
    L["lat"], L["lon"] = num(L["latitude"]), num(L["longitude"])
    ref = {c["code"]: c for c in __import__("json").loads((config.BRUT / "ref_communes.json").read_text(encoding="utf-8"))}
    conc = lire(ed / "concordance_cmp_sae.csv")
    conc = conc[conc["niveau"] == "dep"].set_index("code")
    epci = lire(ed / "lieux_soins_epci.csv")[["code"]]

    def km(lon, lat, g):
        r = np.radians
        a = np.sin(r(g["lat"] - lat) / 2) ** 2 + np.cos(r(lat)) * np.cos(r(g["lat"])) * np.sin(r(g["lon"] - lon) / 2) ** 2
        return 6371 * 2 * np.arcsin(np.sqrt(a))

    lignes = []
    for _, s in signaux[signaux["type"].isin(["cmp_adultes", "cmp_enfants"])].iterrows():
        ty, t = f"lieu_{s['type']}", s["type"].split("_")[1]
        if s["niveau"] == "commune":
            communes, dep = [s["code"]], s["dep"]
        else:
            communes = sorted(L.loc[L["epci"] == s["code"], "commune"].unique()) or []
            communes = [c for c, u in ref.items() if u.get("_epci") == s["code"]] or communes
            dep = L.loc[L["epci"] == s["code"], "dep"].mode().iloc[0] if (L["epci"] == s["code"]).any() else ""
        # centre : la commune elle-même, ou la plus peuplée de l'intercommunalité qui a des structures inscrites
        if s["niveau"] == "commune":
            c0 = s["code"]
        else:
            ici = L[L["epci"] == s["code"]]
            c0 = max(ici["commune"].unique(), key=lambda c: (ref.get(c) or {}).get("population", 0)) if len(ici) else ""
        proches = ""
        if c0 in C:
            lon, lat = C[c0][0], C[c0][1]
            g = L[(L["type"] == ty) & L["lat"].notna()].copy()
            g["km"] = km(lon, lat, g)
            g = g.nsmallest(2, "km")
            proches = " | ".join(f"{r.nom[:50]} ({r.nom_commune}, {r.km:.1f} km, {r.provenance})" for r in g.itertuples())
        zone_ = L[(L["epci"] == s["code"]) if s["niveau"] != "commune" else (L["commune"] == s["code"])]
        app = zone_[zone_["type"].isin(APPARENTES)]
        dep = dep or (zone_["dep"].iloc[0] if len(zone_) else "")
        cc = conc.loc[dep] if dep in conc.index else None
        gest = L[(L["type"] == ty) & (L["dep"] == dep)].groupby("entite_juridique").size().sort_values(ascending=False)
        lignes.append({**s.to_dict(), "dep": dep, "centre": (ref.get(c0) or {}).get("nom", c0),
                       "plus_proches": proches,
                       "psychiatrie_inscrite_ici": " | ".join(f"{r.libelle_type[:40]} : {r.nom[:50]} ({r.provenance})"
                                                             for r in app.itertuples())[:1500],
                       "dep_ici": "" if cc is None else cc[t], "dep_sae": "" if cc is None else cc[f"sae_{t}"],
                       "gestionnaires_dep": " ".join(f"{k}:{v}" for k, v in gest.items())})
    return pd.DataFrame(lignes)


def com_sae(c: str) -> str:
    """Code commune de la SAE ramené au code officiel : la SAE écrit 9A101 pour 97101 (Guadeloupe), et de même 9B,
    9C, 9D, 9F pour la Martinique, la Guyane, La Réunion et Mayotte (config.SAE_DEPARTEMENTS_OUTRE_MER)."""
    from pipeline import config
    if isinstance(c, str) and c[:2] in config.SAE_DEPARTEMENTS_OUTRE_MER:
        return "97" + c[2:] if len(c) == 5 else c
    return c


SAE_DOSSIER = Path(r"D:\offre_soins_tmp\sae2024")
# sites qui déclarent l'activité dans la SAE 2024 (bases statistiques de la DREES, jeu 708, Licence Ouverte) : la
# référence indépendante la plus fine, établissement géographique par établissement géographique, avec sa commune
SAE_SITES = {"maternite": ("PERINAT", lambda t, n: n(t.SEJACC) > 0, "accouchements"),
             "urgences": ("URGENCES2", lambda t, n: n(t.PASSU) > 0, "passages aux urgences"),
             "dialyse": ("DIALYSE", lambda t, n: (n(t.CAPA) > 0) | (n(t.NBPAT) > 0), "postes ou patients"),
             "had": ("HAD", lambda t, n: n(t.SEJ_HAD) > 0, "séjours d'HAD"),
             "smr": ("SSR", lambda t, n: (n(t.LIT) > 0) | (n(t.PLA) > 0), "lits ou places"),
             # bordereau PSY : un site qui déclare des places d'hôpital de jour dans la discipline ; le lieu de
             # l'hôpital de jour peut être distinct du site déclarant (limite écrite dans la note)
             "hdj_psy_adultes": ("PSY", lambda t, n: (t.DIS == "GEN") & (n(t.CAP_HDJ) > 0), "places d'hôpital de jour, psychiatrie générale"),
             "hdj_psy_enfants": ("PSY", lambda t, n: (t.DIS == "INF") & (n(t.CAP_HDJ) > 0), "places d'hôpital de jour, psychiatrie infanto-juvénile")}


def etape3(ed: Path, signaux: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Concordance site par site avec la SAE pour les types hospitaliers qu'elle décrit par établissement géographique,
    et classement des signaux de ces types : si la SAE n'a aucun site du type dans la commune (ou l'intercommunalité)
    non plus, l'absence est confirmée par une source indépendante ; sinon, le site de la SAE est à rapprocher."""
    if not SAE_DOSSIER.exists():
        return {}
    P = {q.name.split("_2024")[0]: q for q in SAE_DOSSIER.rglob("*.csv")}
    from pipeline import config
    P["PSY"] = config.BRUT / "sae" / "psy.csv"
    rd = lambda k: pd.read_csv(P[k], sep=";", encoding="latin-1", dtype=str, keep_default_na=False)  # noqa: E731
    n = lambda s: pd.to_numeric(s.str.replace(",", "."), errors="coerce").fillna(0)  # noqa: E731
    ID = rd("ID").drop_duplicates("fi").set_index("fi")
    L = lire(ed / "lieux_soins.csv")
    c2e = lire(ed / "accessibilite_communes.csv", usecols=["code", "epci"]).drop_duplicates("code").set_index("code")["epci"]
    res, cls, man = [], [], []
    for t, (k, filtre, quoi) in SAE_SITES.items():
        s = rd(k)
        s = s[filtre(s, n)]
        s = s.drop_duplicates("FI")
        fi = set(s.FI.str.zfill(9))
        x = L[L["type"] == f"lieu_{t}"]
        lf = set(x["finess"]) | set(x["finess_rapproche"]) | {a for v in x["finess_absorbes"] for a in v.split() if a}
        lf.discard("")
        com = {f: (com_sae(ID.loc[f, "COMINSEE"]) if f in ID.index else "") for f in fi}
        manq = sorted(fi - lf)
        for f in manq:
            autres = L[(L["finess"] == f) | (L["finess_rapproche"] == f) | L["finess_absorbes"].str.contains(f, regex=False)]
            man.append({"type": t, "fi": f, "nom_sae": ID.loc[f, "rs"] if f in ID.index else "", "commune": com[f],
                        "nom_commune_sae": ID.loc[f, "LIBCOM"] if f in ID.index else "",
                        "meme_commune_dans_la_liste": bool(com[f]) and bool((x["commune"] == com[f]).any()),
                        "cas": ("a : site dans la liste sous d'autres types" if len(autres) else
                                "d : site absent de la liste"),
                        "types_dans_la_liste": ", ".join(sorted(autres["libelle_type"].unique()))[:300]})
        # (b) même site, même type, placé dans une autre commune que celle de la SAE
        for _, r in x[x["finess"].isin(fi)].iterrows():
            if com.get(r["finess"]) and r["commune"] != com[r["finess"]]:
                man.append({"type": t, "fi": r["finess"], "nom_sae": ID.loc[r["finess"], "rs"] if r["finess"] in ID.index else "",
                            "commune": com[r["finess"]], "nom_commune_sae": ID.loc[r["finess"], "LIBCOM"] if r["finess"] in ID.index else "",
                            "meme_commune_dans_la_liste": False,
                            "cas": f"b : placé à {r['nom_commune']} ({r['commune']}), {r['emplacement']}",
                            "types_dans_la_liste": ""})
        mt = [m for m in man if m["type"] == t]
        res.append({"type": t, "sites_sae": len(fi), "structures_liste": len(x), "sae_absents_liste": len(manq),
                    "dont_meme_commune": sum(m["meme_commune_dans_la_liste"] for m in mt if not m["cas"].startswith("b")),
                    "absents_sous_autres_types": sum(m["cas"].startswith("a") for m in mt),
                    "absents_de_la_liste": sum(m["cas"].startswith("d") for m in mt),
                    "places_autre_commune": sum(m["cas"].startswith("b") for m in mt),
                    "critere_sae": quoi})
        coms_sae = {c for c in com.values() if c}
        epci_sae = {c2e.get(c, "") for c in coms_sae}
        # la SAE localise l'activité au site déclarant : juste pour une maternité, des urgences, une unité de dialyse
        # ou un service de réadaptation ; un hôpital de jour de psychiatrie peut être déclaré par l'hôpital dont il
        # dépend, et l'HAD soigne au domicile depuis des antennes : pour eux, l'absence dans la SAE ne prouve rien
        localise = t not in ("hdj_psy_adultes", "hdj_psy_enfants", "had")
        for _, r in signaux[signaux["type"] == t].iterrows():
            ici = (r["code"] in coms_sae) if r["niveau"] == "commune" else (r["code"] in epci_sae)
            # une structure du type déjà dans la commune, loin du centre de sa population (Orléans, La Source) :
            # géographie de la commune, pas un manque
            dans = r["niveau"] == "commune" and bool((x["commune"] == r["code"]).any())
            cls.append({**r.to_dict(), "sae_site_ici": ici, "liste_dans_la_commune": dans,
                        "cause": "c" if dans else "a_rapprocher" if ici else "e" if localise else "a_recouper",
                        "source": f"SAE 2024, bordereau {k}, sites déclarant des {quoi}",
                        "remarque": ("la liste a déjà une structure du type dans la commune, loin du centre de sa population"
                                     if dans else "la SAE a un site du type ici, absent de la liste à cet endroit" if ici else
                                     "aucun site du type ici dans la SAE non plus : absence confirmée par une source indépendante"
                                     if localise else "la SAE ne localise pas ce type au lieu de soins : à recouper sur une autre source")})
    return {"etape3_concordance_sites_sae": pd.DataFrame(res), "etape3_sites_sae_absents_liste": pd.DataFrame(man),
            "etape3_signaux_hospitaliers_classes": pd.DataFrame(cls)}


# colonnes du RPPS lues pour la piste M4 : jamais les noms, prénoms, civilités ni coordonnées de contact (règles du
# projet, partie 3) ; l'identifiant sert seulement à compter des personnes distinctes et n'est jamais écrit
RPPS_COLONNES = {1: "id", 10: "profession", 16: "savoir_faire", 18: "mode", 19: "siret", 21: "finess_site",
                 22: "finess_ej", 23: "id_structure", 24: "raison_sociale", 25: "enseigne", 28: "numero",
                 31: "type_voie", 32: "voie", 36: "commune", 37: "nom_commune"}
MOTIF_PSY = r"\bc\.?m\.?p\b|medico[- ]?psycho|pedopsy|psychiatr|secteur|\bcattp\b|\bcmpea\b|\bcmpi\b"


def piste_rpps(ed: Path) -> dict[str, pd.DataFrame]:
    """M4 : lieux d'exercice déclarés au RPPS par les professionnels de psychiatrie des établissements qui déclarent des
    CMP à la SAE, ou dont la raison sociale ou l'enseigne cite un CMP ou la psychiatrie. Un lieu est un indice, jamais
    une preuve : il compte au moins trois personnes distinctes, et il est dans une commune où la liste n'a aucune
    structure de psychiatrie du même établissement. Le lieu déclaré est souvent l'hôpital de rattachement : une absence
    d'indice ne prouve rien."""
    import re
    import unicodedata
    from pipeline import config
    src = config.BRUT / "rpps_activite.txt"
    cols = sorted(RPPS_COLONNES)
    e = lire(ed / "concordance_cmp_etablissements.csv")
    ejs = set(e.loc[(num(e["sae_cmp"]).fillna(0) > 0) | (num(e["sae_cattp"]).fillna(0) > 0), "ej"])
    simple = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()  # noqa: E731
    parts = []
    for ch in pd.read_csv(src, sep="|", usecols=cols, dtype=str, keep_default_na=False, encoding="utf-8",
                          chunksize=400_000, quoting=3):
        ch.columns = [RPPS_COLONNES[c] for c in cols]
        txt = (ch["raison_sociale"] + " " + ch["enseigne"]).map(simple)
        garde = ch["finess_ej"].isin(ejs) | txt.str.contains(MOTIF_PSY, regex=True)
        prof = ch["profession"].map(simple)
        psy = (prof.str.contains("medecin") & ch["savoir_faire"].map(simple).str.contains("psychiatr")) |             prof.str.contains("infirmier") | prof.str.contains("psychologue")
        parts.append(ch[garde & psy])
    R = pd.concat(parts, ignore_index=True)
    R["groupe"] = R["profession"].map(simple).map(lambda p: "psychiatre" if "medecin" in p else
                                                  "infirmier" if "infirmier" in p else "psychologue")
    R["lieu"] = R["siret"].where(R["siret"] != "", R["id_structure"])
    R["adresse"] = (R["numero"] + " " + R["type_voie"] + " " + R["voie"]).str.strip()
    agg = (R.groupby(["finess_ej", "lieu", "commune"])
           .agg(nom_commune=("nom_commune", "first"), raison_sociale=("raison_sociale", "first"),
                enseigne=("enseigne", "first"), adresse=("adresse", "first"), finess_site=("finess_site", "first"),
                personnes=("id", "nunique"),
                psychiatres=("id", lambda s: s[R.loc[s.index, "groupe"] == "psychiatre"].nunique()),
                infirmiers=("id", lambda s: s[R.loc[s.index, "groupe"] == "infirmier"].nunique()),
                psychologues=("id", lambda s: s[R.loc[s.index, "groupe"] == "psychologue"].nunique()))
           .reset_index())
    agg = agg[agg["personnes"] >= 3]
    L = lire(ed / "lieux_soins.csv")
    psy_types = set(APPARENTES)
    Lp = L[L["type"].isin(psy_types)]
    couverts = set(zip(Lp["entite_juridique"], Lp["commune"]))
    agg["liste_a_une_structure_ici"] = [(ej, c) in couverts for ej, c in zip(agg["finess_ej"], agg["commune"])]
    ind = agg[~agg["liste_a_une_structure_ici"] & (agg["finess_ej"] != "")]
    resume = pd.DataFrame([{"activites_lues": len(R), "lieux_3_personnes_ou_plus": len(agg),
                            "indices_commune_sans_structure_du_meme_etablissement": len(ind)}])
    return {"etape4_rpps_lieux": agg.drop(columns=[]), "etape4_rpps_indices": ind, "etape4_rpps_resume": resume}


PMI_FICHIER = Path(r"D:\offre_soins_tmp\pmi\PMI_2024_ACTIVITE_BRUT.xlsx")


def etape5(ed: Path) -> dict[str, pd.DataFrame]:
    """M5 : un rapport à une référence indépendante par département et par type, puis le nombre de départements dans
    chaque état pour plusieurs seuils. Pour les CMP et les CATTP, nombre inscrit sur nombre déclaré à la SAE ; pour les
    types que la SAE décrit par site, part des sites de la SAE retrouvés dans la liste ; pour les PMI, nombre inscrit sur
    points fixes de consultation déclarés à la DREES. Les autres types n'ont pas de référence : « non vérifiable »."""
    L = lire(ed / "lieux_soins.csv")
    lignes = []
    c = lire(ed / "concordance_cmp_sae.csv")
    c = c[c["niveau"] == "dep"]
    for t, ici, sae in (("cmp_adultes", "adultes", "sae_adultes"), ("cmp_enfants", "enfants", "sae_enfants")):
        for _, r in c.iterrows():
            lignes.append({"type": t, "dep": r["code"], "liste": num(pd.Series([r[ici]]))[0],
                           "reference": num(pd.Series([r[sae]]))[0], "mesure": "nombre / SAE"})
    # CATTP : nombre déclaré à la SAE par département (bordereau PSY)
    from pipeline import config
    psy = pd.read_csv(config.BRUT / "sae" / "psy.csv", sep=";", encoding="latin-1", dtype=str, keep_default_na=False)
    psy = psy[psy["DIS"].isin(["GEN", "INF"])]
    ID = pd.read_csv(next(SAE_DOSSIER.rglob("ID_2024r.csv")), sep=";", encoding="latin-1", dtype=str,
                     keep_default_na=False).drop_duplicates("fi").set_index("fi") if SAE_DOSSIER.exists() else None
    def dep_fi(f):
        c = com_sae(ID.loc[f, "COMINSEE"]) if ID is not None and f in ID.index else ""
        return (c[:3] if c.startswith("97") else c[:2]) if c else ""
    psy["dep"] = psy["FI"].str.zfill(9).map(dep_fi)
    cattp = psy.groupby("dep")["NB_CATTP"].apply(lambda s: num(s).sum())
    n_cattp = L[L["type"] == "lieu_cattp"].groupby("dep").size()
    for d, v in cattp.items():
        if d:
            lignes.append({"type": "cattp", "dep": d, "liste": float(n_cattp.get(d, 0)), "reference": float(v),
                           "mesure": "nombre / SAE"})
    # types que la SAE décrit par site : part des sites retrouvés
    if ID is not None:
        P = {q.name.split("_2024")[0]: q for q in SAE_DOSSIER.rglob("*.csv")}
        P["PSY"] = config.BRUT / "sae" / "psy.csv"
        n_ = lambda s: pd.to_numeric(s.str.replace(",", "."), errors="coerce").fillna(0)  # noqa: E731
        for t, (k, filtre, _q) in SAE_SITES.items():
            s = pd.read_csv(P[k], sep=";", encoding="latin-1", dtype=str, keep_default_na=False)
            s = s[filtre(s, n_)].drop_duplicates("FI")
            x = L[L["type"] == f"lieu_{t}"]
            lf = set(x["finess"]) | set(x["finess_rapproche"]) | {a for v in x["finess_absorbes"] for a in v.split() if a}
            s["dep"] = s["FI"].str.zfill(9).map(dep_fi)
            s["trouve"] = s["FI"].str.zfill(9).isin(lf)
            for d, g in s.groupby("dep"):
                if d:
                    lignes.append({"type": t, "dep": d, "liste": float(g["trouve"].sum()), "reference": float(len(g)),
                                   "mesure": "sites SAE retrouvés / sites SAE"})
    # PMI
    if PMI_FICHIER.exists():
        p_ = pd.read_excel(PMI_FICHIER, dtype=str)
        n_pmi = L[L["type"] == "lieu_pmi"].groupby("dep").size()
        for _, r in p_.iterrows():
            d = r["Code_Dep"]
            ref = pd.to_numeric(r["GENERAL_C13_2024"], errors="coerce")
            if d in ("69D", "69M"):   # Rhône et Métropole de Lyon réunis, comme dans la liste
                continue
            lignes.append({"type": "pmi", "dep": d, "liste": float(n_pmi.get(d, 0)), "reference": float(ref),
                           "mesure": "nombre / points fixes DREES"})
        r69 = p_[p_["Code_Dep"].isin(["69D", "69M"])]["GENERAL_C13_2024"].map(lambda v: pd.to_numeric(v, errors="coerce")).sum()
        lignes.append({"type": "pmi", "dep": "69", "liste": float(n_pmi.get("69", 0)), "reference": float(r69),
                       "mesure": "nombre / points fixes DREES"})
    E = pd.DataFrame(lignes)
    E["rapport"] = E["liste"] / E["reference"].where(E["reference"] > 0)
    seuils = []
    for t, g in E.groupby("type"):
        for s_ in (.5, .7, .8, .9):
            seuils.append({"type": t, "seuil": s_, "departements": len(g),
                           "incomplets": int((g["rapport"] < s_).sum()),
                           "sans_reference": int(g["rapport"].isna().sum())})
    return {"etape5_rapport_par_departement": E, "etape5_effet_des_seuils": pd.DataFrame(seuils)}


ACT_FICHIER = Path(r"D:\offre_soins_tmp\finess_act\activites_exercees.csv")
# activités exercées par établissement géographique, flux FINESS+ « FINESS - Activités » de l'ANS (data.gouv.fr, jeu
# finess-activites-1, Licence Ouverte 2.0, instantané mensuel d'octobre 2026) ; codes lus dans les nomenclatures de
# l'ANS (TRE R381 activités, R382 modalités, R383 mentions, guide des terminologies de santé, version 20260330) et,
# pour les autorisations à l'ancien format, dans « Activités modalités formes utilisées dans FINESS » (data.gouv.fr,
# jeu finess-extraction-des-principales-nomenclatures). Lus le 16 novembre 2026.
AUTORISATIONS = {
    "urgences": [("AMM", "QA014", {"MO032", "MO033"}), ("AMF", "14", {"23", "24"})],
    "maternite": [("AMM", "QA003", {"MO016"}), ("AMF", "03", None)],
    "dialyse": [("AMM", "QA016", {"MO020", "MO021", "MO022", "MO023"}), ("AMF", "16", {"40", "41", "42", "43", "44"})],
    "had": [("AMM", "QA020", None)],
    "smr": [("AMM", "QA050", None), ("AMF", "50", None), ("AMF", "51", None), ("AMF", "52", None), ("AMF", "53", None),
            ("AMF", "54", None), ("AMF", "55", None), ("AMF", "56", None), ("AMF", "57", None), ("AMF", "58", None),
            ("AMF", "59", None)],
}


def etape6(ed: Path) -> dict[str, pd.DataFrame]:
    """Concordance avec les autorisations d'activités de soins exercées, site par site, à jour de novembre 2026 : la
    référence la plus récente pour les types hospitaliers (la SAE décrit 2024, un site sur trois a changé depuis)."""
    if not ACT_FICHIER.exists():
        return {}
    A = pd.read_csv(ACT_FICHIER, sep=";", dtype=str, keep_default_na=False)
    A = A[(A["etat"] == "A") & (A["fin_effective"] == "null")]
    L = lire(ed / "lieux_soins.csv")
    res, det = [], []
    for t, regles in AUTORISATIONS.items():
        m = pd.Series(False, index=A.index)
        for nat, act, mods in regles:
            m |= (A["nature"] == nat) & (A["activite"] == act) & (A["modalite"].isin(mods) if mods else True)
        aut = set(A.loc[m, "finess_et"])
        x = L[L["type"] == f"lieu_{t}"]
        lf = set(x["finess"]) | set(x["finess_rapproche"]) | {a for v in x["finess_absorbes"] for a in v.split() if a}
        lf.discard("")
        absents = sorted(aut - lf)
        for f in absents:
            autres = L[(L["finess"] == f) | (L["finess_rapproche"] == f)]
            det.append({"type": t, "finess_et": f, "nom": autres["nom"].iloc[0] if len(autres) else "",
                        "commune": autres["nom_commune"].iloc[0] if len(autres) else "",
                        "dans_la_liste_sous": ", ".join(sorted(autres["libelle_type"].unique()))[:200]})
        res.append({"type": t, "sites_autorises": len(aut), "structures_liste": len(x),
                    "autorises_absents_de_la_liste": len(absents),
                    "dont_inscrits_sous_d_autres_types": sum(1 for d in det if d["type"] == t and d["dans_la_liste_sous"]),
                    "numeros_de_la_liste_sans_autorisation": len(lf - aut)})
    return {"etape6_concordance_autorisations": pd.DataFrame(res), "etape6_autorises_absents_liste": pd.DataFrame(det)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", default=None)
    ap.add_argument("--rpps", action="store_true", help="piste RPPS seule (exécution lourde)")
    a = ap.parse_args()
    eds = sorted(p for p in (R / "resultats").iterdir() if p.is_dir() and p.name[:2] == "20")
    ed = R / "resultats" / a.edition if a.edition else eds[-1]
    if a.rpps:
        out = R / "docs" / "structures" / f"mesure_{dt.date.today().isoformat()}"
        out.mkdir(parents=True, exist_ok=True)
        for n_, t in piste_rpps(ed).items():
            t.to_csv(out / f"{n_}.csv", sep=";", index=False, encoding="utf-8-sig")
            print(n_, len(t))
        return 0
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
    tables.update(etape1(ed))
    tables.update(etape2(ed))
    tables["etape2_contexte_cmp"] = contexte_cmp(ed, tables["etape2_signaux"])
    tables.update(etape3(ed, tables["etape2_signaux"]))
    tables.update(etape5(ed))
    tables.update(etape6(ed))
    for n, t in tables.items():
        t.to_csv(out / (f"{n}.csv" if n.startswith("etape") else f"etape0_{n}.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")
    for k, v, ok in lignes:
        print(f"{k:38} {v!s:>40}  {ok}")
    print(f"\nÉdition {ed.name}, {ecarts} écart(s) avec la fiche. Dossier {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
