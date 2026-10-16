"""Confirmation des structures par des listes officielles indépendantes de FINESS et du ROR (décision de Lucas du
13 octobre 2026, « qu'à la fin on n'ait plus de doute »).

Deux listes, tirées automatiquement à chaque mise à jour.
- Les sites que chaque établissement déclare à sa certification par la HAS (sources/has_certification.py). Un CMP
  dont un numéro FINESS (le sien, celui d'une inscription rapprochée ou réunie) est un site de certification dont le
  nom désigne un CMP est confirmé.
- Les établissements de son gestionnaire inscrits au répertoire Sirene sous une enseigne de CMP
  (sources/sirene.py), dans la même commune. Quand une commune en compte plusieurs, ils sont appariés un à un par les
  mots du nom, le public (enfants ou adultes) et la rue. L'adresse de Sirene est gardée à côté.

Les structures vérifiées sur les sources de leur établissement gardent leur statut. Les établissements Sirene actifs
sans correspondant sont listés à part, à vérifier, jamais ajoutés d'eux-mêmes (un hôpital ferme rarement ses anciens
établissements dans Sirene).
"""
from __future__ import annotations

import re

import pandas as pd

from . import config
from .util import JOURNAL

NIVEAUX = {"etablissement": "vérifiée sur les sources de l'établissement",
           "source_publique": "vérifiée sur une autre source publique (HAS, ARS, Acceslibre)",
           "has_sirene": "confirmée par la certification HAS et par Sirene",
           "has": "confirmée par la certification HAS",
           "sirene": "confirmée par Sirene",
           "examinee": "examinée à la main et maintenue (source dans la colonne examen)",
           "bases": "inscrite dans FINESS ou le ROR, à vérifier"}
VIDES = {"cmp", "centre", "medico", "psychologique", "cattp", "hdj", "hopital", "jour", "de", "du", "des", "la", "le",
         "les", "et", "adultes", "adulte", "enfants", "enfant", "secteur", "ch", "chs", "epsm", "psychiatrie",
         "consultations", "consultation", "infanto", "juvenile", "pole", "ado", "ados", "adolescents", "intersecteur"}


def _simple(s) -> str:
    from .lieux import _simple as s_
    return s_(s)


def _mots(x) -> set[str]:
    return {w for w in _simple(x).split() if w not in VIDES and len(w) > 2 and not w.isdigit()}


def _nums(r) -> set[str]:
    out = set()
    for c in ("finess", "finess_rapproche", "finess_absorbes"):
        v = r.get(c)
        if isinstance(v, str) and v:
            out |= set(v.split(","))
    return out


def confirmer(lieux: pd.DataFrame, has: dict | None, sir: dict | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajoute à chaque structure d'un type confirmé (config.SIRENE_ENSEIGNES) les colonnes confirmee_has, siret_sirene,
    enseigne_sirene, adresse_sirene et confirmation (niveau). Renvoie les structures et les établissements Sirene actifs
    sans correspondant."""
    x = lieux.copy()
    for c in ("confirmee_has", "siret_sirene", "enseigne_sirene", "adresse_sirene", "confirmation"):
        x[c] = None
    sans = []
    enfants_de = {t[0]: t[4]["parent"] for t in config.LIEUX_TYPES if t[4].get("parent")}
    for tid, motif in config.SIRENE_ENSEIGNES.items():
        m = x["type"] == tid
        g = x[m]
        # certification HAS, sites dont le nom désigne ce type
        if has is not None:
            s = has["sites"]
            eg = set(s.loc[s["RS_eg"].fillna("").str.contains(motif, case=False, regex=True), "FINESS_EG"])
            x.loc[m, "confirmee_has"] = [bool(_nums(r) & eg) for _, r in g.iterrows()]
        # Sirene, établissements actifs du même gestionnaire, même commune, enseigne du type
        if sir is not None:
            e = sir["etablissements"]
            e = e[(e["etatAdministratifEtablissement"] == "A") & e["enseigne"].str.contains(motif, case=False, regex=True)]
            par_siren = {k: v for k, v in e.groupby("siren")}
            pub = x[x["type"].isin([k for k, v in enfants_de.items() if v == tid])].groupby("lieu")["type"].apply(set)
            for ej, ge in g.groupby("ej"):
                cand_ej = par_siren.get(sir["siren"].get(ej))
                if cand_ej is None:
                    continue
                pris = set()
                for i, r in ge.iterrows():
                    cand = cand_ej[(cand_ej["codeCommuneEtablissement"] == r["commune"]) & ~cand_ej["siret"].isin(pris)]
                    if cand.empty:
                        continue
                    nom = r.get("nom") if isinstance(r.get("nom"), str) else r.get("nom_finess")
                    publics = pub.get(r["lieu"], set())
                    sc = {}
                    for k, cr in cand.iterrows():
                        enf = bool(re.search(r"ENFAN|INFANT|ADO|PEDO|JEUN", cr["enseigne"], re.I))
                        sc[k] = (len(_mots(nom) & _mots(cr["enseigne"]))
                                 + 2 * (bool(r.get("adresse")) and _simple(str(r.get("adresse")))[-10:] in _simple(cr["adresse"]))
                                 + ((enf and "lieu_cmp_enfants" in publics) or (not enf and "lieu_cmp_adultes" in publics)))
                    seuls = len(cand) == 1 and (ge["commune"] == r["commune"]).sum() == 1
                    k = max(sc, key=sc.get)
                    if sc[k] > 0 or seuls:
                        pris.add(cand.at[k, "siret"])
                        x.loc[i, ["siret_sirene", "enseigne_sirene", "adresse_sirene"]] = \
                            [cand.at[k, "siret"], cand.at[k, "enseigne"], cand.at[k, "adresse"]]
                reste = cand_ej[~cand_ej["siret"].isin(pris)]
                for _, cr in reste.iterrows():
                    sans.append({"type": tid, "ej": ej, "siret": cr["siret"], "enseigne": cr["enseigne"],
                                 "adresse": cr["adresse"], "commune": cr["codeCommuneEtablissement"],
                                 "date_creation": cr.get("dateCreationEtablissement")})
        # niveau de confirmation
        st = x.loc[m, "statut_verification"] if "statut_verification" in x else pd.Series(None, index=g.index)
        h = x.loc[m, "confirmee_has"].fillna(False).astype(bool)
        si = x.loc[m, "siret_sirene"].notna()
        niv = pd.Series("bases", index=g.index, dtype=object)
        niv[si] = "sirene"
        niv[h] = "has"
        niv[h & si] = "has_sirene"
        niv[st.isin(["etablissement", "source_publique"])] = st[st.isin(["etablissement", "source_publique"])]
        x.loc[m, "confirmation"] = niv
        # les CMP pour adultes et pour enfants prennent le niveau de leur CMP « tous publics »
        par_lieu = x.loc[m].drop_duplicates("lieu").set_index("lieu")
        for enf, par in enfants_de.items():
            if par != tid:
                continue
            me = x["type"] == enf
            for c in ("confirmee_has", "siret_sirene", "enseigne_sirene", "adresse_sirene", "confirmation"):
                x.loc[me, c] = x.loc[me, "lieu"].map(par_lieu[c])
        n = niv.value_counts()
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Confirmation des structures, {lib}",
                         f"{len(g)} structures, " + ", ".join(f"{NIVEAUX[k]} {int(n.get(k, 0))}" for k in NIVEAUX)
                         + f", établissements Sirene actifs sans correspondant {sum(1 for s_ in sans if s_['type'] == tid)}")
    return x, pd.DataFrame(sans, columns=["type", "ej", "siret", "enseigne", "adresse", "commune", "date_creation"])
