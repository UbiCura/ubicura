"""Évolution de l'offre sur dix ans, par département et par région, d'après les séries de démographie des
professionnels de santé de la DREES tirées du RPPS et les estimations de population de l'INSEE.

La DREES compte chaque professionnel une fois, dans le département de son activité principale. Les régions sont donc
la somme de leurs départements. Seules les séries tirées du RPPS sont retenues (config.EVOLUTION_SERIES), celles du
répertoire ADELI s'interrompent. La densité d'une année rapporte l'effectif au 1er janvier à la population au 1er
janvier de la même année."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config
from .util import JOURNAL


def evolution_densite(n_debut, pop_debut, n_fin, pop_fin):
    """Variation relative de la densité entre deux dates (0,10 pour +10 %). None si une densité de départ est nulle
    ou une donnée manque."""
    vals = [n_debut, pop_debut, n_fin, pop_fin]
    if any(v is None or not np.isfinite(v) for v in vals) or pop_debut <= 0 or pop_fin <= 0 or n_debut <= 0:
        return None
    return (n_fin / pop_fin) / (n_debut / pop_debut) - 1


def calculer(drees: pd.DataFrame | None, pops: pd.DataFrame | None, ref) -> dict:
    """Renvoie {"evolution_offre": table longue, "evolution_offre_resume": une ligne par territoire et profession}."""
    if drees is None or pops is None or drees.empty or pops.empty:
        JOURNAL.controle("Évolution de l'offre", "non calculée, séries de la DREES ou populations absentes")
        return {}
    d0, d1 = config.EVOLUTION_DEBUT, config.EVOLUTION_FIN
    regs = ref.deps.set_index("code")["reg"]
    pop = pops.set_index(["code", "annee"])["population"]
    lignes = []
    for motif, spec, prof, lab in config.EVOLUTION_SERIES:
        x = drees[(drees["motif"] == motif) & (drees["niveau"] == "dep") & drees["effectif"].notna()
                  & drees["spec"].fillna("").map(lambda s: bool(re.search(spec, s)) if spec else s == "")]
        x = x[x["code"].isin(ref.deps["code"])]
        if x.empty:
            continue
        x = x.groupby(["code", "annee"], as_index=False)["effectif"].sum()
        x["population"] = [pop.get((c, a), np.nan) for c, a in zip(x["code"], x["annee"])]
        r = x.assign(code=x["code"].map(regs)).groupby(["code", "annee"], as_index=False)[["effectif", "population"]].sum(min_count=1)
        f = x.groupby("annee", as_index=False)[["effectif", "population"]].sum(min_count=1).assign(code="FR")
        for niv, t in (("FR", f), ("reg", r), ("dep", x)):
            lignes.append(t.assign(niveau=niv, prof=prof, libelle=lab))
    if not lignes:
        return {}
    t = pd.concat(lignes, ignore_index=True)
    t = t[t["annee"].between(d0, d1)]
    t["densite"] = t["effectif"] / t["population"] * 1e4
    t = t[["niveau", "code", "prof", "libelle", "annee", "effectif", "population", "densite"]].sort_values(
        ["prof", "niveau", "code", "annee"]).reset_index(drop=True)
    res = []
    # une série qui commence après d0 (kinésithérapeutes inscrits au RPPS depuis 2017) part de sa première année
    debut = t[t["niveau"] == "FR"].groupby("prof")["annee"].min()
    for (niv, code, prof, lab), g in t.groupby(["niveau", "code", "prof", "libelle"], sort=False):
        a, b = g[g["annee"] == debut[prof]], g[g["annee"] == d1]
        if a.empty or b.empty:
            continue
        a, b = a.iloc[0], b.iloc[0]
        ev = evolution_densite(a["effectif"], a["population"], b["effectif"], b["population"])
        res.append({"niveau": niv, "code": code, "prof": prof, "libelle": lab, "annee_debut": int(debut[prof]), "annee_fin": d1,
                    "effectif_debut": a["effectif"], "effectif_fin": b["effectif"],
                    "densite_debut": a["densite"], "densite_fin": b["densite"], "evolution_densite": ev})
    resume = pd.DataFrame(res)
    for prof, g in resume[resume["niveau"] == "dep"].groupby("prof"):
        fr = resume[(resume["niveau"] == "FR") & (resume["prof"] == prof)]["evolution_densite"]
        JOURNAL.controle(f"Évolution de la densité {int(g['annee_debut'].iloc[0])}-{d1}, {g['libelle'].iloc[0].lower()}",
                         f"France {fr.iloc[0] * 100:+.1f} %, densité en baisse dans "
                         f"{(nb := int((g['evolution_densite'] < 0).sum()))} département{'s' if nb > 1 else ''} sur {g['evolution_densite'].notna().sum()}"
                         if len(fr) and pd.notna(fr.iloc[0]) else "non calculée")
    return {"evolution_offre": t, "evolution_offre_resume": resume, **serie_explorer(drees, pops, ref)}


def _source(motif: str) -> str:
    return ("ADELI" if "adeli" in motif else "SNDS" if "snds" in motif else
            "INSEE, base Tous salariés" if "bts" in motif else "RPPS")


def serie_explorer(drees: pd.DataFrame, pops: pd.DataFrame, ref) -> dict:
    """Toutes les séries de démographie de la DREES par département depuis config.EVOLUTION_DEBUT, pour les
    trajectoires de la page Explorer (26 octobre 2026), chacune avec sa source (RPPS, ADELI jusqu'en 2024, SNDS et base
    Tous salariés pour les infirmiers libéraux et salariés, jamais additionnés). Le total « médecins, toutes
    spécialités » n'est pas repris. Le tableau des rapports (evolution_offre) ne change pas."""
    pop = pops.set_index(["code", "annee"])["population"]
    deps = set(ref.deps["code"])
    lignes = []
    for motif, spec, mode, profs, lab, _def in config.DREES_DEMOGRAPHIE:
        if profs == ["medecins"]:
            continue
        cle = ("chirurgiens" if spec == r"^chirurgie$" else f"{profs[0]}_{mode}" if mode != "all" else profs[0])
        x = drees[(drees["motif"] == motif) & (drees["niveau"] == "dep") & drees["effectif"].notna()
                  & (drees["spec"].fillna("") == (spec or "")) & drees["code"].isin(deps)]
        x = x[x["annee"] >= config.EVOLUTION_DEBUT]
        if x.empty:
            continue
        x = x.groupby(["code", "annee"], as_index=False)["effectif"].sum()
        x["population"] = [pop.get((c, a), np.nan) for c, a in zip(x["code"], x["annee"])]
        lignes.append(x.assign(prof=cle, libelle=lab, source=_source(motif)))
    if not lignes:
        return {}
    t = pd.concat(lignes, ignore_index=True).dropna(subset=["population"])
    JOURNAL.controle("Séries de la page Explorer", f"{t['prof'].nunique()} séries de la DREES par département, dont "
                     f"{t.loc[t['source'] == 'ADELI', 'prof'].nunique()} tirées d'ADELI")
    return {"evolution_explorer": t[["prof", "libelle", "source", "code", "annee", "effectif", "population"]]
            .sort_values(["prof", "code", "annee"]).reset_index(drop=True)}
